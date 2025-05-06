import gradio as gr
from pathlib import Path
import os
import json
import asyncio
import traceback
from datetime import datetime
from typing import Tuple, Optional, Dict
from extractor import process_pdf  # Your modular backend logic

# Configuration
INPUT_DIR = "input_pdfs"
OUTPUT_DIR = "output_results"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
SUPPORTED_TYPES = [".pdf"]

# Create directories
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Custom CSS for enterprise look
CUSTOM_CSS = """
.prose {
    max-width: 100%;
}
.status-box {
    border-radius: 8px;
    padding: 1rem;
    margin: 1rem 0;
}
.success {
    border-left: 4px solid #10B981;
    background-color: #F0FFF4;
}
.error {
    border-left: 4px solid #EF4444;
    background-color: #FEF2F2;
}
.info {
    border-left: 4px solid #3B82F6;
    background-color: #BFDBFE;
}
"""

def format_timestamp():
    """Format current timestamp for display"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def handle_pdf_upload(pdf_file) -> Tuple[Dict, str, str, str]:
    """Process PDF upload with async support and enhanced feedback"""
    status = {
        "status": "Processing...",
        "timestamp": format_timestamp(),
        "step": "Initializing",
        "details": []
    }
    
    try:
        # Step 1: File validation
        status["step"] = "Validating file"
        status["details"].append(f"File size: {pdf_file.size / 1024:.1f} KB")
        
        if not pdf_file.name.lower().endswith(tuple(SUPPORTED_TYPES)):
            raise ValueError(f"Unsupported file type. Supported types: {', '.join(SUPPORTED_TYPES)}")
            
        if pdf_file.size > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum limit of {MAX_FILE_SIZE/1024/1024}MB")

        # Step 2: File save
        status["step"] = "Saving document"
        pdf_path = Path(INPUT_DIR) / f"{datetime.now().timestamp()}_{pdf_file.name}"
        pdf_file.save(pdf_path)
        status["details"].append(f"Saved to: {pdf_path}")

        # Step 3: Document processing
        status["step"] = "Processing document"
        status["details"].append("Running extraction pipeline...")
        
        # Run async processing
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, process_pdf, str(pdf_path))
        
        # Step 4: Result handling
        if not result or "error" in result:
            raise Exception(result.get("error", "Unknown error") if result else "No result returned")
            
        # Find output files
        doc_id = pdf_path.stem
        json_file = Path(OUTPUT_DIR) / f"{doc_id}.json"
        excel_file = Path(OUTPUT_DIR) / f"{doc_id}.xlsx"
        
        # Build JSON preview
        json_preview = ""
        if json_file.exists():
            with open(json_file, "r", encoding="utf-8") as f:
                try:
                    json_data = json.load(f)
                    json_preview = json.dumps(json_data, indent=2)
                except Exception as e:
                    json_preview = f"Error reading JSON: {str(e)}"
        
        # Build model info
        model_used = result.get("Model Used", "Unknown")
        processing_time = result.get("processing_time", "N/A")
        
        model_info = {
            "model_used": model_used,
            "processing_time": processing_time,
            "document_id": doc_id,
            "timestamp": format_timestamp()
        }
        
        # Build status update
        status["status"] = "Success"
        status["step"] = "Completed"
        status["details"].append(f"Processed using {model_used}")
        status["details"].append(f"Output saved to {doc_id}.json")
        
        return {
            "json_output": json_preview,
            "excel_output": str(excel_file) if excel_file.exists() else None,
            "model_info": json.dumps(model_info, indent=2),
            "status": json.dumps(status, indent=2)
        }
        
    except Exception as e:
        # Handle errors gracefully
        error_trace = traceback.format_exc()
        status["status"] = "Error"
        status["step"] = "Failed"
        status["details"].append(str(e))
        status["details"].append("Error trace:")
        status["details"].append(error_trace)
        
        return {
            "json_output": "",
            "excel_output": None,
            "model_info": "",
            "status": json.dumps(status, indent=2)
        }

# Custom components for professional UI
with gr.Blocks(theme=gr.themes.Soft(), css=CUSTOM_CSS) as demo:
    gr.Markdown("# 📑 DataBoss Legal Document Extractor")
    gr.Markdown("## Enterprise-grade document processing with multi-AI model fallback")
    
    with gr.Row():
        with gr.Column(scale=2):
            pdf_upload = gr.File(
                label="Upload Legal Document",
                file_types=[".pdf"],
                height=150
            )
            
            with gr.Accordion("💡 Processing Details", open=False):
                status_box = gr.JSON(label="Processing Status")
            
        with gr.Column(scale=3):
            with gr.Tabs():
                with gr.TabItem("🔍 Extraction Results"):
                    json_output = gr.Code(
                        label="Structured JSON Output",
                        language="json",
                        lines=20
                    )
                
                with gr.TabItem("📊 Excel Export"):
                    excel_output = gr.File(
                        label="Download Excel File",
                        height=200
                    )
                
                with gr.TabItem("🧠 Model Info"):
                    model_info = gr.Code(
                        label="AI Model Details",
                        language="json",
                        lines=10
                    )
    
    
    description = """
    ### How It Works
    1. **Upload**: Submit your legal PDF document
    2. **Process**: 
       - Intelligent OCR extraction
       - Multi-model AI processing (Qwen3 → Claude → GPT-4)
       - Field validation and normalization
    3. **Export**: Get structured data in JSON and Excel
    
    ### Features
    ✅ Enterprise-grade security  
    ✅ Multi-AI model fallback  
    ✅ Audit-ready outputs  
    ✅ GDPR-compliant processing
    """
    gr.Markdown(description)
    
    # Event handler
    pdf_upload.change(
        fn=handle_pdf_upload,
        inputs=[pdf_upload],
        outputs=[
            json_output,
            excel_output,
            model_info,
            status_box
        ]
    )

if __name__ == "__main__":
    demo.launch()
