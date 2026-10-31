import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from jinja2 import Template
from playwright.sync_api import sync_playwright
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials as UserCredentials
from google.auth.transport.requests import Request
import pickle
from dotenv import load_dotenv
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
load_dotenv()

def get_user_drive_creds():
    """Gets OAuth credentials for your personal Google Account to handle Drive uploads."""
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    creds = None
    
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'oauth_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    return creds

def upload_to_drive(file_path, folder_id, user_creds):
    """Uploads a file to a specific Google Drive folder and returns its shareable link."""
    try:
        service = build('drive', 'v3', credentials=user_creds)
        
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(
            file_path, 
            mimetype='application/pdf', 
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        service.permissions().create(
            fileId=file.get('id'),
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
        
        return file.get('webViewLink')
    except Exception as e:
        print(f"❌ Drive upload failed for {file_path}: {e}")
        return None

def generate_pdf_and_sheet(
    company_name, 
    job_position, 
    career_objective, 
    cover_letter_body,
    job_link,
    recipient_name="",  # <-- Added recipient_name here
    job_nature="Full time",
    job_type="Remote",
    company_location="",
    job_status="no response",
    how_applied="email",
    comment="",
    drive_folder_id=""
):
    if not os.path.exists("generated_resumes"):
        os.makedirs("generated_resumes")
        
    current_date = datetime.now().strftime("%B %d, %Y")

    # ==========================================
    # 1. GENERATE RESUME PDF
    # ==========================================
    with open("resume_template.html", "r", encoding="utf-8") as f:
        resume_template_content = f.read()
    rendered_resume_html = Template(resume_template_content).render(
        job_position=job_position,
        career_objective=career_objective
    )
    resume_pdf_filename = f"generated_resumes/AbdullahMSiam_Resume_{company_name}_{job_position}.pdf"
    
    # ==========================================
    # 2. GENERATE COVER LETTER PDF
    # ==========================================
    with open("cover_letter_template.html", "r", encoding="utf-8") as f:
        cover_template_content = f.read()
    rendered_cover_html = Template(cover_template_content).render(
        date=current_date,
        recipient_name=recipient_name,  # <-- Passed to template
        company_name=company_name,
        company_location=company_location,
        job_position=job_position,
        cover_letter_body=cover_letter_body
    )
    cover_pdf_filename = f"generated_resumes/AbdullahMSiam_CoverLetter_{company_name}_{job_position}.pdf"

    # ==========================================
    # 3. RENDER BOTH PDFS
    # ==========================================
    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        page_resume = browser.new_page()
        page_resume.set_content(rendered_resume_html)
        page_resume.pdf(
            path=resume_pdf_filename, format="A4", print_background=True,
            margin={"top": "0in", "bottom": "0in", "left": "0in", "right": "0in"}
        )
        
        page_cover = browser.new_page()
        page_cover.set_content(rendered_cover_html)
        page_cover.pdf(
            path=cover_pdf_filename, format="A4", print_background=True,
            margin={"top": "0in", "bottom": "0in", "left": "0in", "right": "0in"}
        )
        
        browser.close()
        
    print(f"\n✅ Resume PDF created: {resume_pdf_filename}")
    print(f"✅ Cover Letter PDF created: {cover_pdf_filename}")

    # ==========================================
    # 4. AUTHENTICATE (Service Account for Sheets)
    # ==========================================
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        sheet_creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    except Exception as e:
        print(f"❌ Service Account Authentication failed: {e}")
        return

    # ==========================================
    # 5. UPLOAD TO GOOGLE DRIVE (Using Personal OAuth)
    # ==========================================
    resume_drive_link = ""
    cover_drive_link = ""

    if drive_folder_id:
        print("\n⏳ Uploading to Google Drive (using your personal account)...")
        try:
            user_creds = get_user_drive_creds()
            
            resume_drive_link = upload_to_drive(resume_pdf_filename, drive_folder_id, user_creds) or "Upload failed"
            cover_drive_link = upload_to_drive(cover_pdf_filename, drive_folder_id, user_creds) or "Upload failed"
            
            if resume_drive_link != "Upload failed":
                print(f"☁️  Resume → {resume_drive_link}")
            if cover_drive_link != "Upload failed":
                print(f"☁️  Cover Letter → {cover_drive_link}")
        except Exception as e:
            print(f"❌ Drive upload process failed: {e}")
    else:
        print("⚠️ No Drive folder ID provided. Skipping upload.")

    # ==========================================
    # 6. UPDATE GOOGLE SHEET (Using Service Account)
    # ==========================================
    try:
        client = gspread.authorize(sheet_creds)
        sheet = client.open("Abdullah Muhammad Siam -Job tracker").sheet1
        
        today = datetime.now().strftime("%d, %B").lstrip("0")
        formatted_job_link = f'=HYPERLINK("{job_link}", "{job_link}")'

        # Only display the clickable Resume link. 
        if resume_drive_link and resume_drive_link != "Upload failed":
            resume_cell = f'=HYPERLINK("{resume_drive_link}", "Resume Link")'
        else:
            resume_cell = os.path.basename(resume_pdf_filename)

        row_data = [
            today,                 # 1. Date
            company_name,          # 2. Company
            job_position,          # 3. Position
            resume_cell,           # 4. Resume Drive (Resume Link only)
            job_nature,            # 5. Job Nature
            job_type,              # 6. Job Type
            company_location,      # 7. Company Location
            formatted_job_link,    # 8. Job link
            job_status,            # 9. Job status
            how_applied,           # 10. How Applied
            comment                # 11. Comment
        ]

        existing_rows = len(sheet.get_all_values())
        next_row = existing_rows + 1

        sheet.insert_row(row_data, index=next_row, value_input_option="USER_ENTERED")
        sheet.copy_range(f"A2:K2", f"A{next_row}:K{next_row}", paste_type="PASTE_FORMAT")

        print(f"✅ Google Sheet updated at row {next_row}!")
        
    except Exception as e:
        print(f"❌ Google Sheet update failed: {e}")

def get_input(prompt, default=""):
    if default:
        val = input(f"{prompt} (Default: '{default}'): ").strip()
        return val if val else default
    else:
        val = input(f"{prompt}: ").strip()
        while not val:
            print("⚠️ This field is required!")
            val = input(f"{prompt}: ").strip()
        return val

if __name__ == "__main__":
    try:
        drive_folder_id = os.getenv("DRIVE_FOLDER_ID", "")
        
        print("--- Job Application Automation ---")
        company = get_input("Company Name")
        position = get_input("Job Position (e.g. Software Engineer)")
        job_link = get_input("Job Link")
        
        # Added prompt for Recipient Name
        recipient = input("Hiring Manager Name (Optional, press Enter to skip): ").strip()
        
        print("\nCareer Objective (For Resume):")
        objective = input("> ").strip()
        while not objective:
            objective = input("> ").strip()

        print("\nCover Letter Body (Paste your text. Type 'END' on a new line to finish):")
        cover_lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            cover_lines.append(line)
        cover_body = "\n".join(cover_lines)

        print("\n--- Options ---")
        job_nature = get_input("Job Nature [Full time / Internship / Constructual]", default="Full time")
        job_type = get_input("Job Type [Remote / Onsite / Hybrid]", default="Remote")
        location = input("Company Location (Optional): ").strip()
        how_applied = get_input("How Applied [email / google form]", default="email")
        comment = input("Comment (Optional): ").strip()

        generate_pdf_and_sheet(
            company_name=company,
            job_position=position,
            career_objective=objective,
            cover_letter_body=cover_body,
            job_link=job_link,
            recipient_name=recipient,  # <-- Added here to pass the input
            job_nature=job_nature,
            job_type=job_type,
            company_location=location,
            job_status="no response",
            how_applied=how_applied,
            comment=comment, 
            drive_folder_id=drive_folder_id
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 Process cancelled by user. Exiting gracefully...")