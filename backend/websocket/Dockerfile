FROM python:3.12-slim

WORKDIR /app

# Install SUMO and system dependencies
RUN apt-get update && apt-get install -y \
    sumo \
    sumo-tools \
    sumo-doc \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set SUMO_HOME so SUMO can find its environment (critical for Docker)
ENV SUMO_HOME=/usr/share/sumo
# Add SUMO binaries to PATH
ENV PATH=$SUMO_HOME/bin:$PATH

# Copy the entire repo so backend/ package is available
COPY . /app

# Install Python requirements
COPY diagnostic/requirements_pinned.txt .
RUN pip install -r requirements_pinned.txt
RUN pip install fastapi uvicorn[standard] traci websockets

# Set Python path so imports work
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Run the FastAPI app with explicit SUMO_HOME
CMD ["uvicorn", "backend.websocket.app:app", "--host", "0.0.0.0", "--port", "8000"]
