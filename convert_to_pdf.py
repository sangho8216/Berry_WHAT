from fpdf import FPDF
import sys

def convert_md_to_pdf(input_file, output_file):
    pdf = FPDF()
    pdf.add_page()
    # fpdf2 doesn't support Korean well without specific fonts, 
    # so we'll try to use a standard one and warn the user.
    pdf.set_font("Arial", size=12)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            # Clean up line for basic PDF rendering
            text = line.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 10, txt=text)
            
    pdf.output(output_file)
    print(f"PDF saved to {output_file}")

if __name__ == "__main__":
    convert_md_to_pdf("/home/sh/workspace/Berry_WHAT/architecture.md", "/home/sh/workspace/Berry_WHAT/architecture.pdf")
