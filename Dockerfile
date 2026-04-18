FROM python:3.10-slim

# Set up a new user named "user" with user ID 1000
RUN useradd -m -u 1000 user

# Switch to the "user" user
USER user

# Set home to the user's home directory
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

# Set the working directory to the user's home directory
WORKDIR $HOME/app

# Copy the requirements file into the container
COPY --chown=user requirements.txt .

# Install dependencies (ignoring warnings generally)
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the application files into the container
COPY --chown=user . .

# Expose port 7860 which is the requirement for Hugging Face Spaces
EXPOSE 7860

# Run the backend
CMD ["python", "-u", "app.py"]
