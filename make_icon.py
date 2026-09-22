from keypointer.art import draw_tray_icon

draw_tray_icon(256).save(
    "keypointer.ico",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)