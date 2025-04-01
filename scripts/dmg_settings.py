# DMG Settings for Agentic

# Volume format (best compression)
format = 'UDBZ'
volume_name = "Agentic Installer"

# Files to include
files = [ 'dist/Agentic.app' ]

# Create a link to the Applications folder
symlinks = { 'Applications': '/Applications' }

# Arrange icons on the DMG
icon_locations = {
    'Agentic.app': (140, 120),
    'Applications': (400, 120)
}

# Window config
window_rect = ((100, 100), (540, 300))

# Icon size in the window
icon_size = 80

# Background
background = 'builtin-arrow'
