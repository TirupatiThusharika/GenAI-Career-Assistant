from flask import Flask, render_template, request
import os
import fitz
import json
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Upload folder
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Connect to Gemini
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_resume():

    # Get uploaded resume
    resume = request.files.get("resume")

    # Check if file exists
    if not resume:
        return "No resume selected."

    if resume.filename == "":
        return "No resume selected."

    # Allow only PDF
    if not resume.filename.lower().endswith(".pdf"):
        return "Please upload a PDF file."

    # Save resume
    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        resume.filename
    )

    resume.save(file_path)

    # --------------------------------
    # EXTRACT TEXT FROM PDF
    # --------------------------------

    pdf = fitz.open(file_path)

    resume_text = ""

    for page in pdf:
        resume_text += page.get_text()

    pdf.close()

    if not resume_text.strip():
        return "Could not extract text from this PDF."

    # --------------------------------
    # GEMINI PROMPT
    # --------------------------------

    prompt = f"""
You are an AI Career Assistant.

Analyze the resume below and return ONLY valid JSON.

Use exactly these keys:

{{
    "resume_score": 0,
    "score_reason": "",
    "education": [],
    "skills": [],
    "experience": [],
    "recommended_roles": [],
    "skill_gaps": [],
    "learning_roadmap": []
}}

Rules:

1. resume_score:
   - Give an overall resume score from 0 to 100.
   - Consider education, technical skills, experience,
     projects, relevance, clarity and career readiness.
   - This is an AI-generated estimate.

2. score_reason:
   - Give a short explanation of why the resume received this score.

3. education:
   - Include important education details found in the resume.

4. skills:
   - Include technical skills found in the resume.

5. experience:
   - Include internships, jobs and relevant experience.

6. recommended_roles:
   - Suggest suitable career roles based only on the resume.

7. skill_gaps:
   - Mention important skills the candidate should improve.

8. learning_roadmap:
   - Give practical steps the candidate can follow.

Important rules:

- Use short, clear bullet-style strings.
- Do not invent information.
- If information is missing, return an empty array.
- Return ONLY valid JSON.
- Do not use markdown.
- Do not add ```json.
- Do not add explanations outside the JSON.

RESUME:

{resume_text}
"""

    # --------------------------------
    # SEND RESUME TO GEMINI
    # --------------------------------

    response = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt
    )

    # Get Gemini response
    analysis_text = response.output_text.strip()

    # --------------------------------
    # CLEAN GEMINI RESPONSE
    # --------------------------------

    if analysis_text.startswith("```"):
        analysis_text = analysis_text.replace("```json", "")
        analysis_text = analysis_text.replace("```", "")
        analysis_text = analysis_text.strip()

    # --------------------------------
    # CONVERT JSON TO PYTHON
    # --------------------------------

    try:

        analysis = json.loads(analysis_text)

    except json.JSONDecodeError:

        return f"""
        <html>
        <head>
            <title>AI Analysis Error</title>
        </head>

        <body style="
            background:#07111f;
            color:white;
            font-family:Arial;
            padding:40px;
        ">

            <h2>AI response could not be formatted.</h2>

            <pre>{analysis_text}</pre>

        </body>
        </html>
        """

    # --------------------------------
    # SHOW RESULT PAGE
    # --------------------------------

    return render_template(
        "result.html",
        analysis=analysis,
        filename=resume.filename
    )


# --------------------------------
# RUN FLASK APP
# --------------------------------

if __name__ == "__main__":
    app.run(debug=True)