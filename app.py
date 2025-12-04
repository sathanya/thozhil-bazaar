from flask import Flask, json, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv
import os
import re

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# MySQL Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:LocalHost_%401234@localhost/jobportal'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('employee', 'employer'), nullable=False)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    company = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    applications = db.relationship('Application', backref='job', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.Enum('pending', 'approved', 'rejected'), default='pending')
    message = db.Column(db.Text)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    applicant = db.relationship('User', backref='applications')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    application = db.relationship('Application', backref='messages')
    sender = db.relationship('User', backref='messages')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

# Create Database Tables
with app.app_context():
    db.create_all()

# Helper Functions
def validate_mobile(mobile):
    """Validate mobile number format."""
    return re.match(r'^\+?[0-9]{10,15}$', mobile)

def validate_email(email):
    """Validate email format."""
    return re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email)

# Load translations
def load_translations():
    translations = {}
    translations['en'] = json.load(open('translations/en.json', 'r', encoding='utf-8'))
    translations['ta'] = json.load(open('translations/ta.json', 'r', encoding='utf-8'))
    return translations

translations = load_translations()

@app.route('/set_language/<language>', methods=['GET', 'POST'])
def set_language(language):
    # Validate the language
    if language in ['en', 'ta']:
        session['language'] = language
    # Redirect the user back to the previous page or the home page
    return redirect(request.referrer or url_for('job_listing'))

# Get current language translations
def get_translations():
    return translations.get(session.get('language', 'en'), {})


# Login route
@app.route("/", methods=["GET", "POST"])
def login():
    translations = get_translations()
    if request.method == "POST":
        mobile = request.form.get("mobile")
        password = request.form.get("password")
        user = User.query.filter_by(mobile=mobile).first()

        # Compare plaintext password
        if user and user.password == password:
            session['user_id'] = user.id
            session['role'] = user.role
            flash(translations.get("login_successful", "Login successful"), "success")
            return redirect(url_for("job_listing"))
        else:
            flash(translations.get("invalid_credentials", "Invalid credentials"), "error")
    return render_template("login.html", translations=translations)

# Register route
@app.route("/register", methods=["GET", "POST"])
def register():
    translations = get_translations()
    if request.method == "POST":
        name = request.form.get("name")
        mobile = request.form.get("mobile")
        password = request.form.get("password")
        role = request.form.get("role")

        # Validate input
        if not name or not mobile or not password or not role:
            flash(translations.get("all_fields_required", "All fields are required"), "error")
            return redirect(url_for("register"))

        if not validate_mobile(mobile):
            flash(translations.get("invalid_mobile_number", "Invalid mobile number"), "error")
            return redirect(url_for("register"))

        if role not in ["employee", "employer"]:
            flash(translations.get("invalid_role", "Invalid role"), "error")
            return redirect(url_for("register"))

        # Create new user with plaintext password
        new_user = User(name=name, mobile=mobile, password=password, role=role)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash(translations.get("registration_successful", "Registration successful"), "success")
            return redirect(url_for("login"))
        except Exception as e:
            db.session.rollback()
            flash(f"{translations.get('an_error_occurred', 'An error occurred')}: {str(e)}", "error")
    return render_template("register.html", translations=translations)

# Job Listing route
@app.route("/job-listing")
def job_listing():
    translations = get_translations()
    if 'user_id' not in session:
        flash(translations.get("must_be_logged_in_to_view_jobs", "You must be logged in to view job listings"), "error")
        return redirect(url_for("login"))

    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of jobs per page

    # Get filter parameters from the query string
    filter_title = request.args.get("filter_title", "")
    filter_location = request.args.get("filter_location", "")
    filter_date = request.args.get("filter_date", "")

    # Build the query based on filters
    query = Job.query
    if filter_title:
        query = query.filter(Job.title.contains(filter_title))
    if filter_location:
        query = query.filter(Job.location.contains(filter_location))
    if filter_date:
        query = query.filter(Job.posted_at >= filter_date)

    # Paginate the filtered results
    jobs = query.paginate(page=page, per_page=per_page)

    # Fetch applications for the logged-in employee
    applications = Application.query.filter_by(applicant_id=session['user_id']).all()
    applied_job_ids = [app.job_id for app in applications]

    return render_template("job_listing.html", jobs=jobs, applied_job_ids=applied_job_ids, translations=translations)

# Job Posting route
@app.route("/job-posting", methods=["GET", "POST"])
def job_posting():
    translations = get_translations()
    if 'user_id' not in session or session['role'] != 'employer':
        flash(translations.get("not_authorized_to_post_jobs", "You are not authorized to post jobs"), "error")
        return redirect(url_for("job_listing"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        company = request.form.get("company")
        location = request.form.get("location")
        user_id = session['user_id']  # Get user_id from session

        # Check if the user exists
        user = User.query.get(user_id)
        if not user:
            flash(translations.get("invalid_user_please_login_again", "Invalid user. Please log in again."), "error")
            return redirect(url_for("login"))

        new_job = Job(
            title=title,
            description=description,
            company=company,
            location=location,
            user_id=user_id
        )

        try:
            db.session.add(new_job)
            db.session.commit()
            flash(translations.get("job_posted_successfully", "Job posted successfully"), "success")
            return redirect(url_for("job_listing"))
        except Exception as e:
            db.session.rollback()
            flash(f"{translations.get('an_error_occurred', 'An error occurred')}: {str(e)}", "error")
    return render_template("job_posting.html", translations=translations)

# Delete Job route
@app.route("/delete-job/<int:job_id>")
def delete_job(job_id):
    translations = get_translations()
    
    # Check if the user is logged in and is an employer
    if 'user_id' not in session or session['role'] != 'employer':
        flash(translations.get("not_authorized_to_delete_jobs", "You are not authorized to delete jobs"), "error")
        return redirect(url_for("job_listing"))

    # Fetch the job or return a 404 error if not found
    job = Job.query.get_or_404(job_id)
    
    # Ensure the logged-in employer owns the job
    if job.user_id != session['user_id']:
        flash(translations.get("not_authorized_to_delete_this_job", "You are not authorized to delete this job"), "error")
        return redirect(url_for("job_listing"))

    try:
        # Delete all associated applications
        Application.query.filter_by(job_id=job_id).delete()
        
        # Delete the job
        db.session.delete(job)
        db.session.commit()
        
        flash(translations.get("job_deleted_successfully", "Job deleted successfully"), "success")
    except Exception as e:
        db.session.rollback()
        flash(f"{translations.get('an_error_occurred', 'An error occurred')}: {str(e)}", "error")
    
    return redirect(url_for("job_listing"))

# Edit Job route
@app.route("/edit-job/<int:job_id>", methods=["GET", "POST"])
def edit_job(job_id):
    translations = get_translations()
    if 'user_id' not in session or session['role'] != 'employer':
        flash(translations.get("not_authorized_to_edit_jobs", "You are not authorized to edit jobs"), "error")
        return redirect(url_for("job_listing"))

    job = Job.query.get_or_404(job_id)
    
    # Ensure the logged-in employer owns the job
    if job.user_id != session['user_id']:
        flash(translations.get("not_authorized_to_edit_this_job", "You are not authorized to edit this job"), "error")
        return redirect(url_for("job_listing"))

    if request.method == "POST":
        job.title = request.form.get("title")
        job.description = request.form.get("description")
        job.company = request.form.get("company")
        job.location = request.form.get("location")

        try:
            db.session.commit()
            flash(translations.get("job_updated_successfully", "Job updated successfully"), "success")
            return redirect(url_for("job_listing"))
        except Exception as e:
            db.session.rollback()
            flash(f"{translations.get('an_error_occurred', 'An error occurred')}: {str(e)}", "error")

    return render_template("edit_job.html", job=job, translations=translations)

# Apply Job route
@app.route("/apply-job/<int:job_id>", methods=["GET", "POST"])
def apply_job(job_id):
    translations = get_translations()
    if 'user_id' not in session or session['role'] != 'employee':
        flash(translations.get("not_authorized_to_apply_for_jobs", "You are not authorized to apply for jobs"), "error")
        return redirect(url_for("job_listing"))

    if request.method == "POST":
        email = request.form.get("email")
        phone = request.form.get("phone")

        if not validate_email(email):
            flash(translations.get("invalid_email_address", "Invalid email address"), "error")
            return redirect(url_for("apply_job", job_id=job_id))

        new_application = Application(
            job_id=job_id,
            applicant_id=session['user_id'],
            status='pending',
            message="",
            email=email,
            phone=phone
        )

        try:
            db.session.add(new_application)
            db.session.commit()
            flash(translations.get("application_submitted_successfully", "Application submitted successfully"), "success")
            return redirect(url_for("job_listing"))
        except Exception as e:
            db.session.rollback()
            flash(f"{translations.get('an_error_occurred', 'An error occurred')}: {str(e)}", "error")
    return render_template("apply_job.html", job_id=job_id, translations=translations)

# Application Management route
@app.route("/application-management")
def application_management():
    translations = get_translations()
    if 'user_id' not in session or session['role'] != 'employer':
        flash(translations.get("not_authorized_to_view_applications", "You are not authorized to view applications"), "error")
        return redirect(url_for("job_listing"))

    # Fetch jobs posted by the logged-in employer
    jobs = Job.query.filter_by(user_id=session['user_id']).all()
    job_ids = [job.id for job in jobs]

    # Fetch applications for these jobs
    applications = Application.query.filter(Application.job_id.in_(job_ids)).all()

    # Fetch employee details and messages for each application
    application_details = []
    for application in applications:
        job = Job.query.get(application.job_id)
        employee = User.query.get(application.applicant_id)
        messages = Message.query.filter_by(application_id=application.id).all()  # Fetch messages for this application
        application_details.append({
            'application': application,
            'job': job,
            'employee': employee,
            'messages': messages  # Include messages in the details
        })

    return render_template("application_management.html", application_details=application_details, translations=translations)

# Approve Application route
@app.route("/approve-application/<int:application_id>")
def approve_application(application_id):
    translations = get_translations()
    if 'user_id' not in session or session['role'] != 'employer':
        flash(translations.get("not_authorized_to_approve_applications", "You are not authorized to approve applications"), "error")
        return redirect(url_for("job_listing"))

    application = Application.query.get_or_404(application_id)
    application.status = 'approved'

    # Send a default message to the employee
    default_message = Message(
        application_id=application_id,
        sender_id=session['user_id'],  # Employer sends the message
        content=translations.get("application_approved_message", "Your application has been approved.")
    )
    db.session.add(default_message)

    # Notify the employee
    notification = Notification(
        user_id=application.applicant_id,
        message=f"{translations.get('application_approved_notification', 'Your application for job:')} {application.job.title} {translations.get('has_been_approved', 'has been approved.')}"
    )
    db.session.add(notification)

    try:
        db.session.commit()
        flash(translations.get("application_approved_successfully", "Application approved successfully"), "success")
    except Exception as e:
        db.session.rollback()
        flash(f"{translations.get('an_error_occurred', 'An error occurred')}: {str(e)}", "error")
    return redirect(url_for("application_management"))

# Reject Application route
@app.route("/reject-application/<int:application_id>")
def reject_application(application_id):
    translations = get_translations()
    if 'user_id' not in session or session['role'] != 'employer':
        flash(translations.get("not_authorized_to_reject_applications", "You are not authorized to reject applications"), "error")
        return redirect(url_for("job_listing"))

    application = Application.query.get_or_404(application_id)
    application.status = 'rejected'

    # Send a default message to the employee
    default_message = Message(
        application_id=application_id,
        sender_id=session['user_id'],  # Employer sends the message
        content=translations.get("application_rejected_message", "Your application has been rejected.")
    )
    db.session.add(default_message)

    # Notify the employee
    notification = Notification(
        user_id=application.applicant_id,
        message=f"{translations.get('application_rejected_notification', 'Your application for job:')} {application.job.title} {translations.get('has_been_rejected', 'has been rejected.')}"
    )
    db.session.add(notification)

    try:
        db.session.commit()
        flash(translations.get("application_rejected_successfully", "Application rejected successfully"), "success")
    except Exception as e:
        db.session.rollback()
        flash(f"{translations.get('an_error_occurred', 'An error occurred')}: {str(e)}", "error")
    return redirect(url_for("application_management"))

# Send Message route
@app.route("/send-message/<int:application_id>", methods=["POST"])
def send_message(application_id):
    translations = get_translations()
    if 'user_id' not in session:
        flash(translations.get("must_be_logged_in_to_send_messages", "You must be logged in to send messages"), "error")
        return redirect(url_for("login"))

    content = request.form.get("content")
    if not content:
        flash(translations.get("message_content_cannot_be_empty", "Message content cannot be empty"), "error")
        return redirect(url_for("application_management"))

    new_message = Message(
        application_id=application_id,
        sender_id=session['user_id'],
        content=content
    )

    try:
        db.session.add(new_message)
        db.session.commit()
        flash(translations.get("message_sent_successfully", "Message sent successfully"), "success")
    except Exception as e:
        db.session.rollback()
        flash(f"{translations.get('an_error_occurred', 'An error occurred')}: {str(e)}", "error")
    return redirect(url_for("application_management"))

# View Messages route
@app.route("/view-messages/<int:application_id>")
def view_messages(application_id):
    translations = get_translations()
    if 'user_id' not in session:
        flash(translations.get("must_be_logged_in_to_view_messages", "You must be logged in to view messages"), "error")
        return redirect(url_for("login"))

    application = Application.query.get_or_404(application_id)
    messages = Message.query.filter_by(application_id=application_id).all()

    return render_template("view_messages.html", application=application, messages=messages, translations=translations)

# Approved Jobs route
@app.route("/approved-jobs")
def approved_jobs():
    translations = get_translations()
    if 'user_id' not in session or session['role'] != 'employee':
        flash(translations.get("not_authorized_to_view_approved_jobs", "You are not authorized to view approved jobs"), "error")
        return redirect(url_for("job_listing"))

    applications = Application.query.filter_by(applicant_id=session['user_id'], status='approved').all()
    return render_template("approved_jobs.html", applications=applications, translations=translations)

# Logout route
@app.route("/logout")
def logout():
    translations = get_translations()
    session.clear()
    flash(translations.get("logged_out_successfully", "You have been logged out successfully"), "success")
    return redirect(url_for("login"))

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    translations = get_translations()
    return render_template("404.html", translations=translations), 404

# Run the application
if __name__ == "__main__":
    app.run(debug=True)