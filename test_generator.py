from services.watermark.generator import create_glass_watermark


output = create_glass_watermark(
    username="aboobakker_pm",
    video_height=1280,
    output_path="downloads/test_watermark.png",
)

print(f"Watermark created: {output}")