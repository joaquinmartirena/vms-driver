# Tests Fixalia — configurar variables y correr
$env:VMS_PANEL_IP      = "127.0.0.1"
$env:VMS_DEVICE_TYPE   = "fixalia"
$env:VMS_COMMUNITY_READ  = "public"
$env:VMS_COMMUNITY_WRITE = "administrator"

python tests/test_fixalia_driver.py
