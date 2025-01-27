# Dockerfile
FROM python:3.9-slim

# Set working directory
WORKDIR /

# Install dependencies
RUN pip install rpyc sympy numpy flake8

# Copy the server file
COPY utils/python_server.py /

# Run the server
CMD ["python", "python_server.py"]
