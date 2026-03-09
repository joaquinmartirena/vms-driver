# Playground Fixalia — configurar variables y arrancar
$env:VMS_PANEL_IP      = "127.0.0.1"
$env:VMS_DEVICE_TYPE   = "fixalia"
$env:VMS_COMMUNITY_READ  = "public"
$env:VMS_COMMUNITY_WRITE = "administrator"

python tools/message_playground.py
