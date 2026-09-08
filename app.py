import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from jinja2 import Template
from playwright.sync_api import sync_playwright

def generate_pdf_and_sheet(
    company_name, 
    job_position, 
    career_objective, 
    job_link,
    job_nature="Full time",
    job_type="Remote",
    company_location="",
    job_status="no response",
    how_applied="email",
    comment=""
):
    # ১. HTML টেমপ্লেট লোড
    with open("resume_template.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # ২. ডায়নামিক ডেটা রিপ্লেস
    template = Template(template_content)
    rendered_html = template.render(
        job_position=job_position,
        career_objective=career_objective
    )

    # ৩. Playwright দিয়ে PDF তৈরি ও সেভ
    if not os.path.exists("generated_resumes"):
        os.makedirs("generated_resumes")
        
    pdf_filename = f"generated_resumes/AbdullahMSiam_{company_name}_{job_position}.pdf"
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(rendered_html)
        page.pdf(
            path=pdf_filename,
            format="A4",
            print_background=True,
            margin={"top": "0in", "bottom": "0in", "left": "0in", "right": "0in"}
        )
        browser.close()
        
    print(f"\n✅ pdf generated: {pdf_filename}")

# ৪. Google Sheet-এ এন্ট্রি দেওয়া (ওভাররাইটিং মুক্ত সমাধান)
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
    
        sheet = client.open("Abdullah Muhammad Siam -Job tracker").sheet1
        
        today = datetime.now().strftime("%Y-%m-%d")

        row_data = [
            today,             # 1. Date
            company_name,      # 2. Company
            job_position,      # 3. Position
            pdf_filename,      # 4. Resume Drive
            job_nature,        # 5. Job Nature
            job_type,          # 6. Job Type
            company_location,  # 7. Company Location
            job_link,          # 8. Job link
            job_status,        # 9. Job status
            how_applied,       # 10. How Applied
            comment            # 11. Comment
        ]

        # ১. শিটের মোট ব্যবহৃত রো সংখ্যা বের করা
        existing_rows = len(sheet.get_all_values())
        next_row = existing_rows + 1

        # ২. সরাসরি নতুন খালি সারিতে ডাইনামিকভাবে ডাটা ইনসার্ট করা
        sheet.insert_row(row_data, index=next_row, value_input_option="USER_ENTERED")
        print(f"✅ Add new row to Google Sheet {next_row}")
        
    except Exception as e:
        print(f"❌ Google Sheet update failed: {e}")

def get_input(prompt, default=""):
    """optionally get input from user with a default value."""
    if default:
        val = input(f"{prompt} (Default: '{default}'): ").strip()
        return val if val else default
    else:
        val = input(f"{prompt}: ").strip()
        while not val:
            print("⚠️ This field is required! Please enter a value.")
            val = input(f"{prompt}: ").strip()
        return val

if __name__ == "__main__":
    print("--- Job Application Automation ---")
    
    # Required Fields (বাধ্যতামূলক)
    company = get_input("Company Name")
    position = get_input("Job Position (e.g. Software Engineer)")
    job_link = get_input("Job Link")
    
    print("\nCareer Objective (enter/paste text below):")
    objective = input("> ").strip()
    while not objective:
        print("⚠️ Career Objective is required! Please enter a value.")
        objective = input("> ").strip()

    print("\n--- Optional Options (Press Enter to select default value) ---")
    
    # Optional Fields with Defaults
    job_nature = get_input("Job Nature [Full time / Internship / Constructual]", default="Full time")
    job_type = get_input("Job Type [Remote / Onsite / Hybrid]", default="Remote")
    location = input("Company Location (Optional): ").strip()
    how_applied = get_input("How Applied [email / google form]", default="email")
    comment = input("Comment (Optional): ").strip()

    # Default job_status is automatically set to "no response"
    generate_pdf_and_sheet(
        company_name=company,
        job_position=position,
        career_objective=objective,
        job_link=job_link,
        job_nature=job_nature,
        job_type=job_type,
        company_location=location,
        job_status="no response",
        how_applied=how_applied,
        comment=comment
    )