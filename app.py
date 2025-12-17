import re
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from num2words import num2words
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import csv
import io
from whitenoise import WhiteNoise
import os
import json

app = Flask(__name__)
app.secret_key = 'your_super_secret_key'

# 'static' folder ko serve karne ke liye app ko WhiteNoise se wrap karein
app.wsgi_app = WhiteNoise(app.wsgi_app, root="static/", prefix="/static/")

# This function is still needed for vendor management.
def init_db():
    """Initializes the database and creates the vendors table if it doesn't exist."""
    conn = sqlite3.connect('vendors.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            gstin TEXT,
            address TEXT,
            bank_name TEXT,
            account_no TEXT,
            branch TEXT,
            ifsc TEXT,
            mobile TEXT,
            payid TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('vendors.db')
    conn.row_factory = sqlite3.Row
    return conn

def parse_nrega_data(text):
    data = {'material_items': []}
    patterns = {
        'district': r"District:([\w\s]+)",
        'work_description': r"Work\s*:\s*(.+?)\s*Work Code",
        'work_code': r"Work Code\s*:\s*([\w/\-]+)",
        'bill_no': r"Bill No\.\s*:\s*(\d+)",
        'bill_date': r"Bill Date\s*:\s*(\d{2}/\d{2}/\d{4})",
        'vendor_raw': r"Vendor name(.+?)\(TinNo-([\w]+)\)"
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            if key == 'vendor_raw':
                data['vendor_name'] = match.group(1).strip()
                data['gstin'] = match.group(2).strip()
            else:
                data[key] = match.group(1).strip()

    material_section_match = re.search(r"Material\s+Unit Price.+?\n(.+?)(?=Taxes|Total\s+\(In Rupees\))", text, re.DOTALL | re.IGNORECASE)
    if material_section_match:
        raw_item_text = material_section_match.group(1).strip()
        item_lines = raw_item_text.strip().split('\n')
        
        for line in item_lines:
            line = re.sub(r'\s+', ' ', line).strip() # Normalize spaces
            if not line: continue

            numbers = re.findall(r'[\d\.]+', line)
            if len(numbers) >= 3:
                try:
                    amount = float(numbers[-1])
                    quantity = float(numbers[-2])
                    unit_price = float(numbers[-3])
                    
                    # To extract the description, we remove the numbers and trailing whitespace
                    desc_part = line.rsplit(numbers[-3], 1)[0].strip()
                    
                    if desc_part: # Ensure we have a description
                        data['material_items'].append({
                            'material': desc_part,
                            'unit_price': unit_price,
                            'quantity': quantity,
                            'amount': amount
                        })
                except (ValueError, IndexError):
                    print(f"Skipping unparsable line chunk: {line}")
                    continue
    
    data['cgst'] = 0.0
    data['sgst'] = 0.0
    cgst_match = re.search(r"Centre GST.*[ \t]([\d\.]+)", text, re.IGNORECASE)
    if cgst_match:
        data['cgst'] = float(cgst_match.group(1))

    sgst_match = re.search(r"State GST.*[ \t]([\d\.]+)", text, re.IGNORECASE)
    if sgst_match:
        data['sgst'] = float(sgst_match.group(1))
        
    total_cash_match = re.search(r"Total Cash payment\s+\(In Rupees\)\s*([\d\.]+)", text, re.IGNORECASE)
    if total_cash_match:
        data['total_cash_payment'] = float(total_cash_match.group(1))

    return data

@app.route('/')
def home():
    """Renders a simple home/dashboard page."""
    return render_template('home.html')

# Original index route renamed to generate_invoice, if you want to keep it as an option
@app.route('/generate-invoice', methods=['GET', 'POST'])
def generate_invoice():
    if request.method == 'POST':
        pasted_data = request.form.get('pasted_data')
        signatures = request.form.getlist('signatures')
        manual_data = {'delivery_note': request.form.get('delivery_note', ''),'terms_of_payment': request.form.get('terms_of_payment', ''),
            'panchayat': request.form.get('panchayat', ''),'block': request.form.get('block', ''),'district': request.form.get('district', '')}
        parsed_data = parse_nrega_data(pasted_data)
        if not parsed_data.get('bill_no') or not parsed_data.get('vendor_name'):
            flash("Could not parse critical details. Please check the pasted text.", 'error'); return redirect(url_for('generate_invoice'))
        for key, value in manual_data.items():
            if value: parsed_data[key] = value
        vendor_name = parsed_data.get('vendor_name', '')
        conn = get_db_connection()
        vendor_details = conn.execute('SELECT * FROM vendors WHERE name = ?', (vendor_name,)).fetchone()
        if not vendor_details:
            flash(f"Vendor '{vendor_name}' not found! Please add their details.", 'warning')
            conn.close()
            return redirect(url_for('manage_vendors', name=vendor_name, gstin=parsed_data.get('gstin', '')))
        vendor_details = dict(vendor_details)
        conn.close()

        subtotal = sum(item['amount'] for item in parsed_data['material_items'])
        grand_total = parsed_data.get('total_cash_payment', subtotal + parsed_data.get('cgst', 0.0) + parsed_data.get('sgst', 0.0))
        final_total_rounded = round(grand_total)
        round_off = final_total_rounded - grand_total
        
        parsed_data['subtotal'] = subtotal
        parsed_data['final_total'] = final_total_rounded
        parsed_data['round_off'] = round_off
        parsed_data['amount_in_words'] = f"Indian Rupees {num2words(final_total_rounded, lang='en_IN').title()} Only."
        parsed_data['signatures'] = signatures
        
        return render_template('preview.html', data=parsed_data, vendor=vendor_details)

    prefill_data = {'delivery_note': request.args.get('delivery_note', ''),'terms_of_payment': request.args.get('terms_of_payment', ''),
        'panchayat': request.args.get('panchayat', ''),'block': request.args.get('block', ''),'district': request.args.get('district', ''),
        'signatures': request.args.getlist('signatures')}
    return render_template('index.html', prefill_data=prefill_data)

@app.route('/muster_roll', methods=['GET', 'POST'])
def generate_muster_roll():
    if request.method == 'POST':
        mr_data = {
            'state': request.form.get('state'), 'mr_no': request.form.get('mr_no'),
            'district': request.form.get('district'), 'block': request.form.get('block'),
            'panchayat': request.form.get('panchayat'), 'financial_year': request.form.get('financial_year'),
            'work_name': request.form.get('work_name'), 'tech_sanction_no': request.form.get('tech_sanction_no'),
            'tech_sanction_date': request.form.get('tech_sanction_date'), 'fin_sanction_no': request.form.get('fin_sanction_no'),
            'fin_sanction_date': request.form.get('fin_sanction_date'), 'work_code': request.form.get('work_code'),
            'agency': request.form.get('agency'), 'mate_name': request.form.get('mate_name'),
            'start_date': request.form.get('start_date'), 'end_date': request.form.get('end_date'),
            'print_date': datetime.now().strftime('%d/%m/%Y')
        }
        
        return render_template('muster_roll_preview.html', data=mr_data)

    return render_template('muster_roll_form.html')

@app.route('/vendors', methods=['GET', 'POST'])
def manage_vendors():
    conn = get_db_connection()
    if request.method == 'POST':
        try:
            conn.execute('INSERT INTO vendors (name, gstin, address, bank_name, account_no, branch, ifsc, mobile, payid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (request.form['name'], request.form['gstin'], request.form['address'], request.form['bank_name'], request.form['account_no'], 
                          request.form['branch'], request.form['ifsc'], request.form['mobile'], request.form['payid']))
            conn.commit()
            flash('Vendor added successfully!', 'success')
        except sqlite3.IntegrityError: flash(f'Vendor "{request.form["name"]}" already exists.', 'error')
        conn.close()
        return redirect(url_for('manage_vendors'))
    vendors = conn.execute('SELECT * FROM vendors ORDER BY name').fetchall()
    conn.close()
    return render_template('vendors.html', vendors=vendors, prefill_name=request.args.get('name', ''), prefill_gstin=request.args.get('gstin', ''))

@app.route('/edit_vendor/<int:vendor_id>', methods=['GET', 'POST'])
def edit_vendor(vendor_id):
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('UPDATE vendors SET name = ?, gstin = ?, address = ?, bank_name = ?, account_no = ?, branch = ?, ifsc = ?, mobile = ?, payid = ? WHERE id = ?',
                     (request.form['name'], request.form['gstin'], request.form['address'], request.form['bank_name'], request.form['account_no'],
                      request.form['branch'], request.form['ifsc'], request.form['mobile'], request.form['payid'], vendor_id))
        conn.commit()
        conn.close()
        flash('Vendor updated successfully!', 'success')
        return redirect(url_for('manage_vendors'))
    
    vendor = conn.execute('SELECT * FROM vendors WHERE id = ?', (vendor_id,)).fetchone()
    conn.close()
    if vendor is None:
        flash('Vendor not found.', 'error')
        return redirect(url_for('manage_vendors'))
    return render_template('edit_vendor.html', vendor=vendor)

@app.route('/delete_vendor/<int:vendor_id>', methods=['POST'])
def delete_vendor(vendor_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM vendors WHERE id = ?', (vendor_id,))
    conn.commit()
    conn.close()
    flash('Vendor deleted successfully.', 'success')
    return redirect(url_for('manage_vendors'))

@app.route('/scheme-list')
def scheme_list():
    return render_template('scheme_list.html')

def parse_job_card_html(html_content):
    """
    Helper function to parse HTML, extract job card data, and the Panchayat name.
    Returns a tuple: (data, panchayat_name, error_message)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    panchayat_name = "default_panchayat"  # Default name if not found

    # Final, more robust method to find the Panchayat name
    try:
        # Find the <b> tag that specifically contains the word "Panchayat"
        panchayat_b_tag = soup.find('b', string='Panchayat')
        if panchayat_b_tag:
            # The full text, including the name, is in the parent <td> tag
            full_text = panchayat_b_tag.parent.get_text(strip=True)
            # The text can look like: "Panchayat(note...): Burkundi"
            # We split by the colon and take the last part, which is the actual name
            if ':' in full_text:
                panchayat_name = full_text.split(':')[-1].strip()
    except Exception:
        # If any error occurs, we'll gracefully fall back to the default name
        pass

    # Find the main data table
    data_table = soup.find('table', {
        'border': '1',
        'width': '100%',
        'bgcolor': 'Floralwhite',
        'style': 'border-collapse:collapse',
        'bordercolor': '#111111'
    })
    
    if not data_table:
        return None, None, "Could not find the data table on the page. The page structure might have changed."

    data_to_csv = []
    rows = data_table.find_all('tr')
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 9 and "Villages" not in row.get_text():
            try:
                applicant_name = cells[3].get_text(strip=True)
                job_card_no = cells[8].get_text(strip=True)
                
                if applicant_name and job_card_no and applicant_name not in ["Name of Applicant", "4"]:
                    data_to_csv.append([applicant_name, job_card_no])
            except IndexError:
                continue
    
    if not data_to_csv:
        return None, None, "No data could be extracted. Please ensure the file contains data in the expected format."
        
    return data_to_csv, panchayat_name, None


@app.route('/applicant-list', methods=['GET', 'POST'])
def applicant_list():
    if request.method == 'POST':
        uploaded_file = request.files.get('html_file')
        user_panchayat_name = request.form.get('panchayat', '').strip()

        if not uploaded_file or uploaded_file.filename == '':
            flash('Please upload an HTML file.', 'error')
            return redirect(url_for('applicant_list'))

        html_content = uploaded_file.read()
        data, detected_panchayat_name, error_message = parse_job_card_html(html_content)
        
        if error_message:
            flash(error_message, 'error')
            return redirect(url_for('applicant_list'))

        # Use user-provided name if available, otherwise use detected name
        if user_panchayat_name:
            panchayat_name = user_panchayat_name
        else:
            panchayat_name = detected_panchayat_name

        # Generate CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name of Applicant', 'Job Card Number'])
        writer.writerows(data)
        output.seek(0)

        # Create dynamic filename as requested
        filename = f"{panchayat_name}_jobcard.csv"
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    return render_template('applicant_list.html')

def parse_work_codes(text):
    """
    Helper function to parse text and extract NREGA work codes.
    Uses the pattern from the desktop app.
    """
    # Regex to find codes like 3422003014/RC/7080901347787
    pattern = re.compile(r'\b(34\d{8}(?:/\w+)+/\d+)\b')
    work_codes = pattern.findall(text)
    return list(dict.fromkeys(work_codes)) # Return unique codes

@app.route('/allocation-list', methods=['GET', 'POST'])
def allocation_list():
    if request.method == 'POST':
        text_data = request.form.get('text_data')
        panchayat_name = request.form.get('panchayat', 'extracted').strip()

        if not text_data:
            flash('Please paste some text to extract codes.', 'error')
            return redirect(url_for('allocation_list'))

        work_codes = parse_work_codes(text_data)
        
        if not work_codes:
            flash('No work codes found in the provided text.', 'warning')
            return redirect(url_for('allocation_list'))

        if not panchayat_name:
            panchayat_name = "extracted"

        # Generate CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Work Code'])
        # Write each code as a new row
        writer.writerows([[code] for code in work_codes])
        output.seek(0)

        # Create dynamic filename
        filename = f"{panchayat_name}_workcodes.csv"
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    return render_template('allocation_list.html')

@app.route('/contractor-list')
def contractor_list():
    """Renders the new tool page for filtering applicant lists."""
    return render_template('contractor_list.html')

@app.route('/scheme-extractor', methods=['GET', 'POST'])
def scheme_extractor():
    if request.method == 'POST':
        raw_text = request.form.get('raw_text', '')
        panchayat_name = request.form.get('panchayat', 'schemes').strip() # Panchayat name
        
        if not raw_text:
            flash("No text provided", "error")
            return redirect(url_for('scheme_extractor'))

        # Regex Update: 
        # 1. re.DOTALL जोड़ा गया है ताकि मल्टी-लाइन नाम (जैसे PMAY वाले) भी कैप्चर हो सकें।
        # 2. कोड पैटर्न को (?:/[A-Z]+)+ किया गया है ताकि /IF/YD/ जैसे एक्स्ट्रा हिस्सों को भी सपोर्ट मिले।
        pattern = re.compile(r'(?:^\d+\s*|\n\d+\s*)?(.*?)\s*(\(34\d{8}(?:/[A-Z]+)+/\d+\))', re.DOTALL)
        matches = pattern.findall(raw_text)
        
        if not matches:
            flash("No valid schemes found in text.", "error")
            return redirect(url_for('scheme_extractor'))

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Scheme Name', 'Work Code'])
        
        count = 0
        for name, code in matches:
            # नाम से एक्स्ट्रा स्पेस और लाइन ब्रेक हटाना
            clean_name = re.sub(r'\s+', ' ', name.strip())
            # अगर नाम के शुरू में कोई सीरियल नंबर बच गया हो तो हटाना
            clean_name = re.sub(r'^\d+\s+', '', clean_name)
            
            clean_code = code.replace('(', '').replace(')', '').strip()
            writer.writerow([clean_name, clean_code])
            count += 1

        output.seek(0)
        
        filename = f"{panchayat_name}_schemes_{count}.csv"
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    return render_template('scheme_extractor.html')

# --- UPDATED: Demand Tool ---
@app.route('/demand-tool', methods=['GET', 'POST'])
def demand_tool():
    if request.method == 'POST':
        data = {
            'panchayat': request.form.get('panchayat', ''),
            'scheme_full_name': request.form.get('scheme_full_name', ''), # Full string from CSV
            'work_code': request.form.get('work_code', ''),
            'date': datetime.now().strftime('%d/%m/%Y'),
            'labourers': []
        }
        
        # Collect dynamic labour rows
        # We assume the form sends rows with index 0 to N
        labour_indices = request.form.getlist('labour_index')
        counter = 1
        for idx in labour_indices:
            name = request.form.get(f'labour_name_{idx}')
            card = request.form.get(f'job_card_{idx}')
            if name or card:
                data['labourers'].append({
                    'sr': counter,
                    'name': name,
                    'card': card
                })
                counter += 1
        
        return render_template('demand_print.html', data=data)
        
    return render_template('demand_form.html')

# --- PUBLIC FILE MANAGER LOGIC ---
PUBLIC_DATA_DIR = os.path.join('static', 'public_data') # Folder structure: static/public_data/District/Block/Panchayat_Master.csv

@app.route('/api/public/locations', methods=['GET'])
def get_public_locations():
    """Returns directory structure for Dropdowns (District -> Block -> Panchayat)"""
    structure = {}
    if not os.path.exists(PUBLIC_DATA_DIR):
        os.makedirs(PUBLIC_DATA_DIR)
        
    # Walk through the directory
    for root, dirs, files in os.walk(PUBLIC_DATA_DIR):
        for file in files:
            if file.endswith('.csv'):
                # Expected path: static/public_data/District/Block/Panchayat.csv
                rel_path = os.path.relpath(os.path.join(root, file), PUBLIC_DATA_DIR)
                parts = rel_path.split(os.sep)
                
                if len(parts) >= 3: # Must be nested properly
                    district = parts[0]
                    block = parts[1]
                    filename = parts[-1]
                    
                    if district not in structure: structure[district] = {}
                    if block not in structure[district]: structure[district][block] = []
                    
                    structure[district][block].append(filename)
    return Response(json.dumps(structure), mimetype='application/json')

@app.route('/api/public/get-file', methods=['POST'])
def get_public_file():
    """Fetches content of a selected public file"""
    data = request.json
    district = data.get('district')
    block = data.get('block')
    filename = data.get('filename')
    
    file_path = os.path.join(PUBLIC_DATA_DIR, district, block, filename)
    
    # Security check to prevent path traversal
    if not os.path.abspath(file_path).startswith(os.path.abspath(PUBLIC_DATA_DIR)):
        return Response("Access Denied", status=403)
        
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return Response(json.dumps({'content': content}), mimetype='application/json')
    return Response("File not found", status=404)
# ---------------------------------

if __name__ == '__main__':
    init_db()
    app.run(debug=True)