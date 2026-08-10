# Use Ubuntu as the base to easily install system packages like FreeCAD
FROM ubuntu:22.04

# Prevent timezone prompts during apt installations
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    freecad \
    xvfb \
    libgl1-mesa-glx \
    libosmesa6 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .

# Upgrade pip and install requirements (allow breaking system packages since it's an isolated container)
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# Copy the rest of the backend code
COPY . .

# Expose the API port
EXPOSE 8000

# Set required environment variables for headless rendering
ENV DISPLAY=:99
ENV PYVISTA_OFF_SCREEN=true
ENV PYVISTA_USE_IPYVTK=false

# Run the API with X virtual framebuffer (xvfb) for headless CAD rendering
CMD ["xvfb-run", "-a", "python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
