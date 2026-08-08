from PIL import Image, ImageOps

# 1. Load the original logo
logo = Image.open('frontend/web-dashboard/public/mercon-logo.png').convert('RGBA')

# Crop to the actual visible content (the logo mark)
bbox = logo.getbbox()
if bbox:
    logo = logo.crop(bbox)

# The user wants a black background for the app icon
icon_size = (1024, 1024)
icon = Image.new('RGBA', icon_size, (0, 0, 0, 255))

# Scale logo to fit nicely in the icon (e.g. 60% of the size)
target_width = int(icon_size[0] * 0.6)
ratio = target_width / float(logo.size[0])
target_height = int(logo.size[1] * ratio)
logo_resized = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)

# Paste logo centered
x = (icon_size[0] - target_width) // 2
y = (icon_size[1] - target_height) // 2
icon.paste(logo_resized, (x, y), logo_resized)

# Save general icon
icon.save('frontend/mobile-app/mercon-app/assets/images/icon.png')

# Save android foreground (transparent background, just the logo)
fg = Image.new('RGBA', icon_size, (0, 0, 0, 0))
fg.paste(logo_resized, (x, y), logo_resized)
fg.save('frontend/mobile-app/mercon-app/assets/images/android-icon-foreground.png')

# Save android monochrome (just white version of the logo on transparent)
r, g, b, a = logo_resized.split()
white_logo = Image.merge('RGBA', (Image.new('L', a.size, 255), Image.new('L', a.size, 255), Image.new('L', a.size, 255), a))
mono = Image.new('RGBA', icon_size, (0, 0, 0, 0))
mono.paste(white_logo, (x, y), white_logo)
mono.save('frontend/mobile-app/mercon-app/assets/images/android-icon-monochrome.png')

# Save android background (pure black)
bg = Image.new('RGBA', icon_size, (0, 0, 0, 255))
bg.save('frontend/mobile-app/mercon-app/assets/images/android-icon-background.png')

# Splash screen icon
# Expo splash screen usually takes a centered image. We can just use the cropped original logo.
logo.save('frontend/mobile-app/mercon-app/assets/images/splash-icon.png')

print("Assets generated successfully!")
