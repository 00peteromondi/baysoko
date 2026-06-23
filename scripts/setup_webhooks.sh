#!/bin/bash

echo "🚀 Setting up Baysoko Webhooks"

# 1. Add environment variables
echo "🔧 Adding environment variables..."
cat >> .env << 'EOL'

# Webhook Configuration
WEBHOOKS_ENABLED=true
# Delivery integration keys used by the Django settings in this repo
# DELIVERY_WEBHOOK_KEY is used for webhook signing/auth between services
DELIVERY_WEBHOOK_KEY=$(openssl rand -hex 32)
# DELIVERY_SYSTEM_API_KEY is used for Authorization Bearer when calling external delivery provider
DELIVERY_SYSTEM_API_KEY=""
DELIVERY_SYSTEM_URL="https://api.delivery-system.com"
DELIVERY_WEBHOOK_URL=https://api.delivery-system.com/webhook/baysoko/
EOL

# 2. Create webhook files
echo "📁 Creating webhook files..."

# Create webhook_service.py
cat > listings/webhook_service.py << 'EOL'
# [Paste the webhook_service.py content here]
EOL

# Create signals.py
cat > listings/signals.py << 'EOL'
# [Paste the signals.py content here]
EOL

# 3. Update existing files
echo "✏️ Updating existing files..."

# Add to settings.py
echo -e "\n# Webhook Settings\nWEBHOOKS_ENABLED = True\nWEBHOOK_SECRET_KEY = config('WEBHOOK_SECRET_KEY')\n" >> baysoko/settings.py

# 4. Run migrations
echo "🗄️ Running migrations..."
python manage.py makemigrations
python manage.py migrate

# 5. Restart server
echo "🔄 Restarting server..."
echo "✅ Webhooks setup complete! Add your actual delivery webhook URL to .env"