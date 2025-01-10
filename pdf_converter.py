from PIL import Image
import os
import re

def convert_images_to_pdf(folder_path):
    # Iterate over each subfolder in the given folder
    for subfolder in os.listdir(folder_path):
        subfolder_path = os.path.join(folder_path, subfolder)
        
        # Only process directories (subfolders)
        if os.path.isdir(subfolder_path):
            print(f"Processing folder: {subfolder_path}")
            
            # Get all images in the subfolder (only .png, .jpg, .jpeg)
            images = []
            for img in os.listdir(subfolder_path):
                img_path = os.path.join(subfolder_path, img)
                if img.lower().endswith(('.png', '.jpg', '.jpeg')):  # Only consider image files
                    base_name = os.path.splitext(img)[0]  # Get base name without extension
                    
                    # Check if a 'n-ans.*' file exists for the image 'n.*'
                    ans_image = f"{base_name}-ans{os.path.splitext(img)[1]}"
                    if ans_image in os.listdir(subfolder_path):
                        images.append(os.path.join(subfolder_path, ans_image))
                    else:
                        images.append(img_path)

            if images:
                # Sort images by numeric part of filename (ignoring '-ans' suffix)
                images.sort(key=lambda x: int(re.match(r'(\d+)', os.path.splitext(os.path.basename(x))[0]).group(1)))

                # Open images and convert to PDF
                image_list = []
                for img_path in images:
                    image = Image.open(img_path)
                    image = image.convert("RGB")  # Convert to RGB for PDF compatibility
                    image_list.append(image)
                
                # Generate the PDF named after the subfolder
                pdf_filename = f"{subfolder}.pdf"
                output_pdf_path = os.path.join(folder_path, pdf_filename)
                image_list[0].save(
                    output_pdf_path,
                    "PDF",
                    resolution=100.0,  # High resolution
		    subsampling=0,
                    save_all=True,
                    append_images=image_list[1:]
                )
                
                print(f"Converted images in {subfolder} to PDF: {output_pdf_path}")
            else:
                print(f"No valid images found in folder: {subfolder_path}")

# Set the folder path
folder_path = r"C:\Users\YLW-LAPTOP\Downloads\2021秋-写作与沟通-103-王沛楠"  # Replace with the path to your folder

# Convert images in subfolders to PDFs
convert_images_to_pdf(folder_path)
