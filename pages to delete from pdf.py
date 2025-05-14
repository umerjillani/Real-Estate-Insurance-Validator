import PyPDF2
import os

def delete_pages_from_pdf(pdf_path, pages_to_delete, output_dir):
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        writer = PyPDF2.PdfWriter()
        
        for i in range(len(reader.pages)):
            if i + 1 not in pages_to_delete:
                writer.add_page(reader.pages[i])
        
        output_path = os.path.join(output_dir, "modified_" + os.path.basename(pdf_path))
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
    
    print(f"Modified PDF saved at: {output_path}")

if __name__ == "__main__":
    pdf_path = r"modified_sample pdf.pdf"
    pages_to_delete = list(map(int, input("Enter page numbers to delete (comma-separated): ").split(',')))
    output_dir = r"C:\Users\pcinf\OneDrive - Higher Education Commission\Intalytic Group\Elevation Ceritificate Project\Comparison"
    
    os.makedirs(output_dir, exist_ok=True)
    delete_pages_from_pdf(pdf_path, pages_to_delete, output_dir)
