from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from firebase_admin import credentials, initialize_app, auth, firestore
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
FIREBASE_API_KEY = "AIzaSyDqlannZbTIy-WDM2ZmiOhsNPP7PzglDT8"  # Clave de API del proyecto Firebase

# Load Firebase credentials from environment variable
firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
if not firebase_credentials_path:
    raise RuntimeError("Environment variable FIREBASE_CREDENTIALS_PATH is not set")

cred = credentials.Certificate(firebase_credentials_path)
initialize_app(cred)
db = firestore.client()

app = FastAPI()

# Models
class User(BaseModel):
    email: str
    password: str
    role: str  # admin, professor, tutor

class Student(BaseModel):
    name: str
    age: int
    school_year: str

class Professor(BaseModel):
    name: str
    subject: str

class SchoolYear(BaseModel):
    year: str
    subjects: List[str]

class Subject(BaseModel):
    name: str
    professor_id: str
    student_ids: List[str]

class Attendance(BaseModel):
    student_id: str
    subject: str
    status: str  # present, absent, justified
    reason: Optional[str] = None

# Secret key and algorithm for JWT
token_secret_key = "your_secret_key"
token_algorithm = "HS256"
token_expiration_minutes = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# Helper function to create JWT token
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=token_expiration_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, token_secret_key, algorithm=token_algorithm)
    return encoded_jwt

# Dependency to get the current user
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, token_secret_key, algorithms=[token_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        user = db.collection("users").document(user_id).get()
        if not user.exists:
            raise HTTPException(status_code=401, detail="User not found")
        return user.to_dict()
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# Authentication Endpoints
from fastapi import APIRouter, HTTPException
from firebase_admin import auth
from pydantic import BaseModel

router = APIRouter()

# Modelos para los endpoints
class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str  # admin, professor, tutor

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register_user(request: RegisterRequest):
    try:
        # Crear usuario en Firebase Authentication
        user = auth.create_user(
            email=request.email,
            password=request.password
        )

        # Guardar información adicional en Firestore
        db.collection("users").document(user.uid).set({
            "email": request.email,
            "role": request.role
        })

        return {"message": "User registered successfully", "user_id": user.uid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
async def login_user(request: LoginRequest):
    try:
        # Realizar una solicitud HTTP al endpoint de autenticación de Firebase
        response = requests.post(
            f"{FIREBASE_AUTH_URL}?key={FIREBASE_API_KEY}",
            json={"email": request.email, "password": request.password, "returnSecureToken": True}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid email or password")

        data = response.json()
        return {
            "idToken": data["idToken"],
            "refreshToken": data["refreshToken"],
            "expiresIn": data["expiresIn"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Include the router for authentication endpoints
app.include_router(router, prefix="/auth", tags=["Authentication"])

# CRUD for Students
@app.post("/students")
def create_student(student: Student):
    student_ref = db.collection("students").add(student.dict())
    return {"id": student_ref[1].id, "message": "Student created successfully"}

@app.get("/students")
def get_students():
    students = [
        {"id": doc.id, **doc.to_dict()}  # Include the document ID in the response
        for doc in db.collection("students").stream()
    ]
    return students

@app.get("/students/{student_id}")
def get_student(student_id: str):
    student = db.collection("students").document(student_id).get()
    if not student.exists:
        raise HTTPException(status_code=404, detail="Student not found")
    return student.to_dict()

@app.put("/students/{student_id}")
def update_student(student_id: str, student: Student):
    student_ref = db.collection("students").document(student_id)
    if not student_ref.get().exists:
        raise HTTPException(status_code=404, detail="Student not found")
    student_ref.update(student.dict())
    return {"message": "Student updated successfully"}

@app.delete("/students/{student_id}")
def delete_student(student_id: str):
    student_ref = db.collection("students").document(student_id)
    if not student_ref.get().exists:
        raise HTTPException(status_code=404, detail="Student not found")
    student_ref.delete()
    return {"message": "Student deleted successfully"}

# CRUD for Professors
@app.post("/professors")
def create_professor(professor: Professor):
    professor_ref = db.collection("professors").add(professor.dict())
    return {"id": professor_ref[1].id, "message": "Professor created successfully"}

@app.get("/professors")
def get_professors():
    professors = [
        {"id": doc.id, **doc.to_dict()}  # Include the document ID in the response
        for doc in db.collection("professors").stream()
    ]
    return professors

@app.get("/professors/{professor_id}")
def get_professor(professor_id: str):
    professor = db.collection("professors").document(professor_id).get()
    if not professor.exists:
        raise HTTPException(status_code=404, detail="Professor not found")
    return professor.to_dict()

@app.put("/professors/{professor_id}")
def update_professor(professor_id: str, professor: Professor):
    professor_ref = db.collection("professors").document(professor_id)
    if not professor_ref.get().exists:
        raise HTTPException(status_code=404, detail="Professor not found")
    professor_ref.update(professor.dict())
    return {"message": "Professor updated successfully"}

@app.delete("/professors/{professor_id}")
def delete_professor(professor_id: str):
    professor_ref = db.collection("professors").document(professor_id)
    if not professor_ref.get().exists:
        raise HTTPException(status_code=404, detail="Professor not found")
    professor_ref.delete()
    return {"message": "Professor deleted successfully"}

# CRUD for School Years
@app.post("/school_years")
def create_school_year(school_year: SchoolYear):
    school_year_ref = db.collection("school_years").add(school_year.dict())
    return {"id": school_year_ref[1].id, "message": "School year created successfully"}

@app.get("/school_years")
def get_school_years():
    school_years = [
        {"id": doc.id, **doc.to_dict()}  # Include the document ID in the response
        for doc in db.collection("school_years").stream()
    ]
    return school_years

@app.get("/school_years/{school_year_id}")
def get_school_year(school_year_id: str):
    school_year = db.collection("school_years").document(school_year_id).get()
    if not school_year.exists:
        raise HTTPException(status_code=404, detail="School year not found")
    return school_year.to_dict()

@app.put("/school_years/{school_year_id}")
def update_school_year(school_year_id: str, school_year: SchoolYear):
    school_year_ref = db.collection("school_years").document(school_year_id)
    if not school_year_ref.get().exists:
        raise HTTPException(status_code=404, detail="School year not found")
    school_year_ref.update(school_year.dict())
    return {"message": "School year updated successfully"}

@app.delete("/school_years/{school_year_id}")
def delete_school_year(school_year_id: str):
    school_year_ref = db.collection("school_years").document(school_year_id)
    if not school_year_ref.get().exists:
        raise HTTPException(status_code=404, detail="School year not found")
    school_year_ref.delete()
    return {"message": "School year deleted successfully"}

# CRUD for Subjects
@app.post("/subjects")
def create_subject(subject: Subject):
    subject_ref = db.collection("subjects").add(subject.dict())
    return {"id": subject_ref[1].id, "message": "Subject created successfully"}

@app.get("/subjects")
def get_subjects():
    subjects = [
        {"id": doc.id, **doc.to_dict()}  # Include the document ID in the response
        for doc in db.collection("subjects").stream()
    ]
    return subjects

@app.get("/subjects/{subject_id}")
def get_subject(subject_id: str):
    subject = db.collection("subjects").document(subject_id).get()
    if not subject.exists:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject.to_dict()

@app.put("/subjects/{subject_id}")
def update_subject(subject_id: str, subject: Subject):
    subject_ref = db.collection("subjects").document(subject_id)
    if not subject_ref.get().exists:
        raise HTTPException(status_code=404, detail="Subject not found")
    subject_ref.update(subject.dict())
    return {"message": "Subject updated successfully"}

@app.delete("/subjects/{subject_id}")
def delete_subject(subject_id: str):
    subject_ref = db.collection("subjects").document(subject_id)
    if not subject_ref.get().exists:
        raise HTTPException(status_code=404, detail="Subject not found")
    subject_ref.delete()
    return {"message": "Subject deleted successfully"}

# Attendance and Notifications
@app.post("/attendance")
def mark_attendance(attendance: Attendance):
    attendance_data = attendance.dict()
    attendance_data["timestamp"] = datetime.utcnow()
    db.collection("attendance").add(attendance_data)

    # Check for 3 absences in the last 7 days
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    absences = db.collection("attendance").where("student_id", "==", attendance.student_id) \
        .where("status", "==", "absent").where("timestamp", ">=", one_week_ago).stream()
    absence_count = len(list(absences))

    if absence_count >= 3:
        student = db.collection("students").document(attendance.student_id).get()
        if student.exists:
            student_name = student.to_dict().get("name", "Unknown")
            notification_message = f"Student {student_name} has 3 absences in the last week."
            db.collection("notifications").add({"message": notification_message, "timestamp": datetime.utcnow()})
            return {"message": "Attendance marked and notification sent", "notification": notification_message}

    return {"message": "Attendance marked successfully"}
