# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . .

# Make port 2455 available to the world outside this container
EXPOSE 2455

# Define environment variable
ENV FLASK_APP app.py

# Run app.py when the container launches using Gunicorn on port 2455
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:2455", "app:app"]