#app.py
from flask import Flask, render_template, make_response
from flask import request, redirect, url_for, Response, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import cv2
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import storage
from detection.face_matching import detect_faces, align_face
from detection.face_matching import extract_features, match_face
from utils.configuration import load_yaml
from datetime import datetime
from fpdf import FPDF

config_file_path = load_yaml("configs/database.yaml")

TEACHER_PASSWORD_HASH = config_file_path["teacher"]["password_hash"]
# print(TEACHER_PASSWORD_HASH)

# Initialize Firebase
cred = credentials.Certificate(config_file_path["firebase"]["pathToServiceAccount"])
firebase_admin.initialize_app(
    cred,
    {
        "databaseURL": config_file_path["firebase"]["databaseURL"],
        "storageBucket": config_file_path["firebase"]["storageBucket"],
    },
)


def upload_database(filename):
    """
    Checks if a file with the given filename already exists in the
    database storage, and if not, uploads the file to the database.
    """
    valid = False
    # If the fileName exists in the database storage, then continue
    if storage.bucket().get_blob(filename):
        valid = True
        error = f"<h1>{filename} already exists in the database</h1>"

    # First check if the name of the file is a number
    if not filename[:-4].isdigit():
        valid = True
        error = f"<h1>Please make sure that the name of the {filename} is a number</h1>"

    if not valid:
        # Image to database
        filename = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        bucket = storage.bucket()
        blob = bucket.blob(filename)
        blob.upload_from_filename(filename)
        error = None

    return valid, error


def match_with_database(img, database):
    '''The function "match_with_database" takes an image and a database as input, detects faces in the
    image, aligns and extracts features from each face, and matches the face to a face in the database.
    '''
    global match
    # Detect faces in the frame
    faces = detect_faces(img)

    # Draw the rectangle around each face
    for x, y, w, h in faces:
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 4)

    # save the image
    cv2.imwrite("static/recognized/recognized.png", img)

    for face in faces:
        try:
            # Align the face
            aligned_face = align_face(img, face)

            # Extract features from the faceF
            embedding = extract_features(aligned_face)

            embedding = embedding[0]["embedding"]

            # Match the face to a face in the database
            match = match_face(embedding, database)

            if match is not None:
                return f"Match found: {match}"
            else:
                return "No match found"
        except:
            return "No face detected"
        # break # TODO: remove this line to detect all faces in the frame


app = Flask(__name__, template_folder="template")
app.secret_key = "123456"  # Add this line

# Specify the directory to save uploaded images
UPLOAD_FOLDER = "static/images"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/")
def home():
    return render_template("welcome.html")

@app.route("/teacher")
def teacher():
    return render_template("teacher.html")

@app.route("/student")
def student():
    return render_template("student.html")

@app.route("/take_attendance")
def take_attendance():
    ref = db.reference("Timetable")
    timetable = ref.get()
    return render_template("take_attendance.html", timetable=timetable)

@app.route("/add_info")
def add_info():
    return render_template("add_info.html")

@app.route("/teacher_register", methods=["GET", "POST"])
def teacher_register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        classes = request.form.getlist("classes")
        password = request.form.get("password")
        
        # Hash the password for security
        hashed_password = generate_password_hash(password)

        # Prepare the data to be saved
        teacher_data = {
            "name": name,
            "email": email,
            "classes": classes,
            "password": hashed_password
        }

        # Save the data to Firebase
        ref = db.reference("Teachers")
        ref.push(teacher_data)

        flash("Registration successful! Please login.")
        return redirect(url_for("teacher_login"))
    return render_template("teacher_register.html")

@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Retrieve all students from Firebase
        ref = db.reference("Students")
        students = ref.get()

        if students:
            # Iterate through the list of students
            for student in students:
                if student and isinstance(student, dict) and student.get("email") == email and student.get("password") == password:
                    # Authentication successful
                    flash("Login successful!")
                    # Redirect to a student-specific page or dashboard
                    return redirect(url_for("take_attendance"))
        
        # Authentication failed
        flash("Incorrect email or password")
    return render_template("student_login.html")

@app.route("/student_register")
def student_register():
    return render_template("home.html")

@app.route("/teacher_login", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Retrieve all teachers from Firebase
        ref = db.reference("Teachers")
        teachers = ref.get()

        # Check each teacher's email and password
        for teacher_id, teacher in teachers.items():
            if teacher["email"] == email and check_password_hash(teacher["password"], password):
                # Authentication successful
                flash("Login successful!")
                return redirect(url_for("attendance"))
        
        # Authentication failed
        flash("Incorrect email or password")
    return render_template("teacher_login.html")


@app.route("/attendance")
def attendance():
    ref = db.reference("Students")
    students_data = ref.get()

    # Check if students_data is None or empty
    if not students_data:
        flash("No attendance data available.")
        return render_template("attendance.html", students={})

    # If there is data, process it
    students = {}
    for index, student_info in enumerate(students_data):
        if student_info and isinstance(student_info, dict):
            students[index] = [
                student_info.get("name"),
                student_info.get("email"),
                student_info.get("userType"),
                student_info.get("classes"),
            ]

    return render_template("attendance.html", students=students)



@app.route("/upload", methods=["POST"])
def upload():
    global filename
    # Check if a file was uploaded
    if "file" not in request.files:
        return "No file uploaded", 400

    file = request.files["file"]

    # Check if the file is one of the allowed types/extensions
    if file.filename == "":
        return "No selected file", 400

    if file and allowed_file(file.filename):
        # Make the filename safe, remove unsupported chars
        filename = secure_filename(file.filename)
        # change the name of the file to the studentId
        # Information to database
        ref = db.reference("Students")
        try:
            # Obtain the last studentId number from the database
            studentId = len(ref.get())
        except TypeError:
            studentId = 1

        filename = f"{studentId}.png"

        # Move the file from the temporal folder to
        # the upload folder we setup
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        # Upload the file to the database
        val, err = upload_database(filename)

        if val:
            return err

        # Redirect the user to the uploaded_file route, which
        # will basically show on the browser the uploaded file
        return redirect(url_for("add_info"))

    return "File upload failed", 400


def allowed_file(filename):
    # Put your allowed file types here
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")  # for browser cache
    # Generate the URL of the image
    url = url_for("static", filename="images/" + filename, v=timestamp)
    # Return an HTML string that includes an <img> tag
    return f'<h1>File uploaded successfully</h1><img src="{url}" alt="Uploaded image">'


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/capture", methods=["POST"])
def capture():
    global filename
    ret, frame = video.read()
    if ret:
        # Information to database
        ref = db.reference("Students")

        try:
            # Obtain the last studentId number from the database
            studentId = len(ref.get())

        except TypeError:
            studentId = 1

        # Save the image
        filename = f"{studentId}.png"
        # Save the frame as an image
        cv2.imwrite(os.path.join(app.config["UPLOAD_FOLDER"], filename), frame)

        # Upload the file to the database
        val, err = upload_database(filename)

        if val:
            return err
    # Redirect to the success page
    return redirect(url_for("add_info"))


@app.route("/success/<filename>")
def success(filename):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")  # for browser cache
    # Generate the URL of the image
    url = url_for("static", filename="images/" + filename, v=timestamp)
    # Return an HTML string that includes an <img> tag
    return f'<h1>{filename} image uploaded successfully to the database</h1><img src="{url}" alt="Uploaded image">'


@app.route("/submit_info", methods=["POST"])
def submit_info():
    # Get the form data
    name = request.form.get("name")
    email = request.form.get("email")
    userType = request.form.get("userType")
    classes = request.form.getlist("classes")  # Get all selected classes
    password = request.form.get("password")

    # Get the last uploaded image
    studentId, _ = os.path.splitext(filename)
    fileName = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    data = cv2.imread(fileName)

    # Detect faces in the image
    faces = detect_faces(data)

    for face in faces:
        # Align the face
        aligned_face = align_face(data, face)

        # Extract features from the face
        embedding = extract_features(aligned_face)
        break

    # Get current timestamp
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Add the information to the database
    ref = db.reference("Students")
    data = {
        str(studentId): {
            "name": name,
            "email": email,
            "userType": userType,
            "classes": {class_: {"attendance": 0, "last_updated": current_time} for class_ in classes},
            "password": password,
            "embeddings": embedding[0]["embedding"],
        }
    }

    for key, value in data.items():
        ref.child(key).set(value)

    return redirect(url_for("success", filename=filename))


@app.route("/recognize", methods=["GET", "POST"])
def recognize():
    global detection
    ret, frame = video.read()
    if ret:
        # Information to database
        ref = db.reference("Students")
        # Obtain the last studentId number from the database
        number_student = len(ref.get())
        print("There are", (number_student - 1), "students in the database")

        database = {}
        for i in range(1, number_student):
            studentInfo = db.reference(f"Students/{i}").get()
            studentName = studentInfo["name"]
            studentEmbedding = studentInfo["embeddings"]
            database[studentName] = studentEmbedding

        detection = match_with_database(frame, database)

    # Return a successful response
    return redirect(url_for("select_class"))


@app.route("/select_class", methods=["GET", "POST"])
def select_class():
    if request.method == "POST":
        # Get the selected class from the form data
        selected_class = request.form.get("classes")

        # Generate the URL of the image
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")  # for browser cache
        url = url_for("static", filename="recognized/recognized.png", v=timestamp)

        # Information to database
        ref = db.reference("Students")
        # Obtain the last studentId number from the database
        number_student = len(ref.get())
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for i in range(1, number_student):
            studentInfo = db.reference(f"Students/{i}").get()
            if match == studentInfo["name"]:
                # Check if the selceted class is in the list of studentInfo['classes']
                print(studentInfo["classes"])
                if selected_class in studentInfo["classes"]:
                    # Update the attendance in the database
                    ref.child(f"{i}/classes/{selected_class}/attendance").set(
                        int(studentInfo.get("classes", {}).get(selected_class, {}).get("attendance", 0)) + 1
                    )
                    ref.child(f"{i}/classes/{selected_class}/last_updated").set(current_time)
                    # Render the template, passing the detection result and image URL
                    return f'<h2>Selected Class: {selected_class} - {detection}</h2><img src="{url}" alt="Recognized face">'
                else:
                    return f'<h2>Student not in class - {detection}</h2><img src="{url}" alt="Recognized face">'
    else:
        # Render the select class page
        return render_template("select_class.html")


@app.route('/attendance/report')
def attendance_report():
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Attendance Report', 0, 1, 'C')

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        def chapter_title(self, num, label):
            self.set_font('Arial', '', 12)
            self.cell(0, 10, f'{num} : {label}', 0, 1)

        def chapter_body(self, body):
            self.set_font('Arial', '', 12)
            self.multi_cell(0, 10, body)

    # Create instance of FPDF class
    pdf = PDF()
    pdf.add_page()

    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Attendance Details", ln=True, align='C')

    # Add a line break
    pdf.ln(10)

    # Fetch students data from Firebase
    ref = db.reference("Students")
    students = ref.get()

    # Table header
    pdf.cell(40, 10, 'Name', 1, 0, 'C')
    pdf.cell(40, 10, 'Email', 1, 0, 'C')
    pdf.cell(30, 10, 'Type', 1, 0, 'C')
    pdf.cell(60, 10, 'Classes', 1, 0, 'C')
    pdf.cell(30, 10, 'Attendance', 1, 0, 'C')
    pdf.cell(60, 10, 'Last Updated', 1, 1, 'C')  # New line after header

    # Iterate over each student
    for student_id, student in enumerate(students[1:], start=1):  # Start from index 1, ignoring the null element
        pdf.cell(40, 10, student['name'], 1, 0)
        pdf.cell(40, 10, student['email'], 1, 0)
        pdf.cell(30, 10, student['userType'], 1, 0)
        
        # Format classes and attendance
        class_details = ', '.join([f"{cls}: {details['attendance']}" for cls, details in student.get('classes', {}).items()])
        pdf.cell(60, 10, class_details, 1, 0)  # Classes and attendance
        
        # Format last updated
        last_updated_details = ', '.join([f"{cls}: {details['last_updated']}" for cls, details in student.get('classes', {}).items()])
        pdf.cell(60, 10, last_updated_details, 1, 0)  # Last updated

        pdf.ln()  # Move to the next line for the next student

    # Save the pdf with name .pdf
    pdf_output = "Attendance_Report.pdf"
    pdf.output(pdf_output)

    # Send the PDF as a response
    with open(pdf_output, "rb") as f:
        pdf_data = f.read()

    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={pdf_output}'
    return response


def gen_frames():
    global video
    video = cv2.VideoCapture(0)
    while True:
        success, frame = video.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode(".jpg", frame)
            frame = buffer.tobytes()
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


if __name__ == "__main__":
    app.run(debug=True)
