from flask import Flask, jsonify, render_template, request, send_file
from state import ResumeState
from transcriber import transcribe_audio
from services.translator import translate_malayalam_to_english
from services.llm import extract_resume_fields, professionalize, process_voice_command
import os
import traceback
import io

app = Flask(__name__)
resume_state = ResumeState()


# -- Pages --

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/resume")
def resume_page():
    data = resume_state.get_resume_data()
    return render_template("resume.html", resume=data)


# -- Core voice pipeline: record -> transcribe -> translate -> extract -> update state --

@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()

    try:
        # Step 1: Sarvam STT  (Malayalam audio -> Malayalam text)
        malayalam_text = transcribe_audio(audio_bytes)

        # Step 2: IndicTrans2  (Malayalam text -> English text)
        try:
            english_text = translate_malayalam_to_english(malayalam_text)
        except Exception as te:
            print(f"[TRANSLATE] {te}")
            english_text = "(Translation unavailable)"

        # Step 3: LLaMA extract  (English text -> structured fields)
        extracted = {}
        if english_text and english_text != "(Translation unavailable)":
            try:
                extracted = extract_resume_fields(english_text)
                resume_state.update(extracted)
                print(f"[EXTRACT] Fields extracted: {list(extracted.keys())}")
            except Exception as ex:
                print(f"[EXTRACT] {ex}")

        return jsonify({
            "transcript": malayalam_text,
            "translation": english_text,
            "extracted": extracted,
            "resume": resume_state.get_resume_data(),
            "missing": resume_state.missing_fields(),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -- Voice command route (delete / edit / add via voice) --

@app.route("/voice-command", methods=["POST"])
def voice_command():
    """Process a voice command that edits/deletes/adds resume data."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_bytes = request.files["audio"].read()

    try:
        # Transcribe & translate the command
        malayalam_text = transcribe_audio(audio_bytes)
        english_text = translate_malayalam_to_english(malayalam_text)

        # Let LLaMA interpret the command
        cmd = process_voice_command(english_text, resume_state.get_resume_data())
        action = cmd.get("action", "unknown")
        field = cmd.get("field")
        details = cmd.get("details")
        value = cmd.get("value")
        index = cmd.get("index")

        result_msg = ""

        if action == "delete" and field:
            ok = resume_state.delete_from_field(field, details=details, index=index)
            result_msg = f"Deleted from '{field}'" if ok else f"Could not delete from '{field}'"

        elif action == "edit" and field and value is not None:
            resume_state.set_field(field, value)
            result_msg = f"Updated '{field}'"

        elif action == "add" and field:
            # For list fields, wrap value and use update
            if isinstance(resume_state.data.get(field), list):
                if isinstance(value, list):
                    resume_state.update({field: value})
                elif isinstance(value, (dict, str)):
                    resume_state.update({field: [value]})
            else:
                resume_state.set_field(field, value)
            result_msg = f"Added to '{field}'"

        else:
            result_msg = f"Command not understood: {details or english_text}"

        return jsonify({
            "transcript": malayalam_text,
            "translation": english_text,
            "command": cmd,
            "message": result_msg,
            "resume": resume_state.get_resume_data(),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -- Manual edit route (from the UI) --

@app.route("/edit", methods=["POST"])
def edit_section():
    payload = request.get_json(force=True)
    field = payload.get("field")
    value = payload.get("value")

    if not field:
        return jsonify({"error": "No field specified"}), 400

    valid_fields = list(resume_state.data.keys())
    if field not in valid_fields:
        return jsonify({"error": f"Invalid field '{field}'. Valid: {valid_fields}"}), 400

    if value is not None:
        resume_state.set_field(field, value)

    return jsonify({
        "message": f"Updated '{field}' successfully.",
        "resume": resume_state.get_resume_data(),
    })


# -- Delete route (from the UI) --

@app.route("/delete", methods=["POST"])
def delete_item():
    payload = request.get_json(force=True)
    field = payload.get("field")
    index = payload.get("index")
    details = payload.get("details")

    if not field:
        return jsonify({"error": "No field specified"}), 400

    ok = resume_state.delete_from_field(field, details=details, index=index)
    return jsonify({
        "success": ok,
        "resume": resume_state.get_resume_data(),
    })


# -- Professionalize the entire resume --

@app.route("/professionalize", methods=["POST"])
def professionalize_resume():
    data = resume_state.get_resume_data()
    if resume_state.is_empty():
        return jsonify({"error": "Resume is empty. Add some data first."}), 400

    try:
        polished = professionalize(data)
        resume_state.replace_all(polished)
        return jsonify({
            "message": "Resume content has been professionalized!",
            "resume": resume_state.get_resume_data(),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Professionalize failed: {e}"}), 500


# -- Get current state --

@app.route("/state", methods=["GET"])
def get_state():
    return jsonify({
        "resume": resume_state.get_resume_data(),
        "missing": resume_state.missing_fields(),
    })


# -- Download PDF --

@app.route("/resume/download")
def resume_download():
    try:
        data = resume_state.get_resume_data()
        html = render_template("resume.html", resume=data)

        import importlib
        import importlib.util
        if importlib.util.find_spec("weasyprint") is not None:
            weasy = importlib.import_module("weasyprint")
            HTML = getattr(weasy, "HTML")
            pdf_bytes = HTML(string=html, base_url=request.host_url).write_pdf()
        elif importlib.util.find_spec("pdfkit") is not None:
            pdfkit = importlib.import_module("pdfkit")
            pdf_bytes = pdfkit.from_string(html, False, options={
                "page-size": "A4",
                "margin-top": "0mm", "margin-bottom": "0mm",
                "margin-left": "0mm", "margin-right": "0mm",
                "encoding": "UTF-8", "enable-local-file-access": None,
            })
        else:
            raise RuntimeError("PDF generation requires 'weasyprint' or 'pdfkit'")

        name = data.get("name") or "resume"
        filename = f"{name.replace(' ', '_')}_Resume.pdf"

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"PDF generation failed: {e}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
