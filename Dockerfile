FROM python:3.11-slim

# Install fonts
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    fonts-dejavu-core \
    wget \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Install Poppins font
RUN mkdir -p /usr/share/fonts/truetype/google-fonts && \
    wget -q "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf" \
         -O /usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf && \
    wget -q "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf" \
         -O /usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf && \
    fc-cache -fv

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
