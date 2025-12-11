import os
import shutil
import fitz  
from rapidocr_onnxruntime import RapidOCR
from django.conf import settings

_OCR_ENGINE = None

def get_model_path(filename):
    return os.path.join(settings.BASE_DIR, 'ocr_models', filename)

def get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        print("Loading OCR Models")
        _OCR_ENGINE = RapidOCR(
            det_model_path=get_model_path('ch_PP-OCRv4_det_infer.onnx'),
            cls_model_path=get_model_path('ch_ppocr_mobile_v2.0_cls_infer.onnx'),
            rec_model_path=get_model_path('ch_PP-OCRv4_rec_infer.onnx'),
            rec_keys_path=get_model_path('ppocr_keys_v1.txt')
        )
    return _OCR_ENGINE

def create_searchable_pdf(input_path, output_path):
    ocr_engine = get_ocr_engine()
    
    temp_output_path = output_path + ".tmp"

    try:
        doc = fitz.open(input_path)
        output_doc = fitz.open()

        for page_num, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
            img_bytes = pix.tobytes("png")
            
            # Run OCR using the shared engine
            ocr_result, _ = ocr_engine(img_bytes)
            
            new_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(new_page.rect, doc, page_num)

            if ocr_result:
                scale_x = page.rect.width / pix.width
                scale_y = page.rect.height / pix.height

                for item in ocr_result:
                    box_points, text, confidence = item
                    xs = [pt[0] for pt in box_points]
                    ys = [pt[1] for pt in box_points]
                    
                    x_min, y_min = min(xs) * scale_x, min(ys) * scale_y
                    x_max, y_max = max(xs) * scale_x, max(ys) * scale_y
                    
                    new_page.insert_text(
                        fitz.Rect(x_min, y_min, x_max, y_max).tl, 
                        text,
                        fontsize=(y_max - y_min), 
                        render_mode=3
                    )

        output_doc.save(temp_output_path)
        output_doc.close()
        doc.close()

        shutil.move(temp_output_path, output_path)
        return "success"

    except Exception as e:
        print(f"Error processing PDF: {e}")
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
        return "failed"
    
get_ocr_engine()  # Preload the OCR engine at module load time