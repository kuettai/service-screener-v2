#!/bin/bash
# Quick rebuild script for Cloudscape UI development
# Rebuilds React app and regenerates HTML without calling AWS APIs

echo "🔄 Quick rebuilding Cloudscape UI..."

# Step 1: Build React app
echo "📦 Building React app..."
cd cloudscape-ui
npm run build
cd ..

# Step 2: Regenerate Cloudscape HTML with existing data
echo "🔧 Regenerating HTML with existing data..."
python3 -c "
import sys
sys.path.insert(0, '.')
from utils.OutputGenerator import OutputGenerator
from utils.Config import Config

# Set up config to get account ID
Config.init()

generator = OutputGenerator(beta_mode=True)
generator.html_folder = 'adminlte/aws/956288449190'
generator.account_id = '956288449190'  # Set account ID explicitly
result = generator._generate_cloudscape()
if result:
    print('✅ Cloudscape HTML regenerated!')
else:
    print('❌ Failed to regenerate Cloudscape HTML')
"

echo "🎉 Quick rebuild complete!"
echo "📂 Open: adminlte/aws/956288449190/index.html"