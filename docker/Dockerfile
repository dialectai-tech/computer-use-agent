# Computer Use Automation - Browser Container
FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Set display environment
ENV DISPLAY=:1
ENV DISPLAY_WIDTH=1280
ENV DISPLAY_HEIGHT=720

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # X11 and display
    xvfb \
    x11vnc \
    fluxbox \
    xterm \
    # Browser dependencies
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    # Utilities
    supervisor \
    python3 \
    python3-pip \
    scrot \
    imagemagick \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages for automation
RUN pip3 install --no-cache-dir \
    playwright==1.48.0 \
    pillow \
    python-xlib

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Create directories
RUN mkdir -p /app /recordings /screenshots /tmp/.X11-unix
RUN chmod 1777 /tmp/.X11-unix

# Create VNC password file
RUN mkdir -p /root/.vnc
RUN x11vnc -storepasswd changeme /root/.vnc/passwd

# Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

WORKDIR /app

# Expose VNC port
EXPOSE 5900

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD DISPLAY=:1 xdpyinfo > /dev/null 2>&1 || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
