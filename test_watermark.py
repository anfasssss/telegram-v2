from services.watermark.engine import add_watermark


input_file = "downloads/DcGsW72yzWq.mp4"

output_file = add_watermark(
    input_file,
    "aboobakker_pm",
    style="glass"
)

print(f"\nOutput saved at: {output_file}")