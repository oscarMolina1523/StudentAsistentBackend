import uvicorn 
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from firebase_admin import credentials, initialize_app, auth, firestore
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv
import json
import time

# Load environment variables from .env file
load_dotenv()

FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
FIREBASE_API_KEY = "AIzaSyDqlannZbTIy-WDM2ZmiOhsNPP7PzglDT8"  # Clave de API del proyecto Firebase

# Cargar credenciales de Firebase desde variables de entorno (Railway)
firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
if firebase_credentials_path and os.path.exists(firebase_credentials_path):
    cred = credentials.Certificate(firebase_credentials_path)
elif os.path.exists("studentasistent-c7cb5-firebase-adminsdk-fbsvc-7861a8208c.json"):
    cred = credentials.Certificate("studentasistent-c7cb5-firebase-adminsdk-fbsvc-7861a8208c.json")
else:
    raise RuntimeError("Firebase credentials are not set in the environment or available as a local file")
initialize_app(cred)
db = firestore.client()


app = FastAPI()
port = 8000

# Models
class User(BaseModel):
    nombre: str
    email: str
    rol: str  # admin, profesor, tutor
    fotoPerfilUrl: Optional[str] = None
    fechaCreacion: datetime
    password: str  # Added password field

class Student(BaseModel):
    nombre: str
    apellido: str
    gradoId: str
    turno: str
    fechaNacimiento: str  # Solo string, sin validación de formato
    activo: bool

class TutorStudentRelation(BaseModel):
    tutorId: str
    alumnoId: str

class Grade(BaseModel):
    nombre: str
    descripcion: str
    imagenUrl: Optional[str] = None
    turno: str  # matutino, vespertino

class Subject(BaseModel):
    nombre: str
    imagenUrl: Optional[str] = None

class GradeSubjectRelation(BaseModel):
    gradoId: str
    materiaId: str
    semestre: int

class ProfessorSubjectRelation(BaseModel):
    profesorId: str
    materiaGradoId: str
    turno: str
    anioEscolar: int

class Attendance(BaseModel):
    alumnoId: str
    materiaId: str
    fecha: datetime
    estado: str  # presente, ausente, justificado
    justificacion: Optional[str] = None
    registradoPor: str
    horaRegistro: str

class Notification(BaseModel):
    alumnoId: str
    tutorId: str
    mensaje: str
    tipo: str  # inasistencia, etc.
    fechaEnvio: datetime
    leido: bool

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
@app.post("/auth/register")
def register_user(user: User):
    password = user.password  # Extract password from the user model

    # Check if user already exists
    existing_user = db.collection("users").where("email", "==", user.email).get()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    # Create user in Firebase Auth with provided password
    firebase_user = auth.create_user(
        email=user.email,
        password=password,  # Use the provided password
        display_name=user.nombre
    )

    # Save user details in Firestore
    user_data = user.dict()
    user_data["uid"] = firebase_user.uid
    user_data["fechaCreacion"] = datetime.utcnow()  # Automatically set creation date
    db.collection("users").document(firebase_user.uid).set(user_data)

    return {"message": "User registered successfully", "userId": firebase_user.uid}

@app.post("/auth/login")
def login_user(email: str, password: str):
    # Firebase Auth login
    try:
        response = requests.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}",
            json={"email": email, "password": password, "returnSecureToken": True}
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=400, detail="Invalid email or password")

@app.put("/auth/edit-profile")
def edit_profile(user_id: str, user: User):
    user_ref = db.collection("users").document(user_id)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user details in Firestore
    user_ref.update(user.dict())

    # Update Firebase Auth user
    auth.update_user(
        user_id,
        email=user.email,
        display_name=user.nombre
    )

    return {"message": "Profile updated successfully"}

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
    print(f"Endpoint de estudiantes: tiene {len(students)} documentos")
    return students

@app.get("/students/paginated")
def get_students_paginated(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    start = time.time()
    students_ref = db.collection("students")
    students_query = students_ref.offset((page - 1) * page_size).limit(page_size).stream()
    students = [
        {"id": doc.id, **doc.to_dict()} for doc in students_query
    ]
    elapsed = time.time() - start
    print(f"Tiempo sin paginación de Estudiantes: 10 segundos | Tiempo con paginación: {elapsed:.2f} segundos")
    return {"page": page, "page_size": page_size, "students": students}

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

# User Endpoints
@app.get("/users/paginated")
def get_users_paginated(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    start = time.time()
    users_ref = db.collection("users")
    users_query = users_ref.offset((page - 1) * page_size).limit(page_size).stream()
    users = [
        {"id": doc.id, **doc.to_dict()} for doc in users_query
    ]
    elapsed = time.time() - start
    print(f"Tiempo sin paginación de Usuarios: 13 segundos | Tiempo con paginación: {elapsed:.2f} segundos")
    return {"page": page, "page_size": page_size, "users": users}

@app.get("/users/{user_id}")
def get_user(user_id: str):
    user = db.collection("users").document(user_id).get()
    if not user.exists:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()

@app.get("/users")
def get_all_users():
    try:
        users_ref = db.collection("users")
        docs = users_ref.stream()

        users = []
        for doc in docs:
            user_data = doc.to_dict()
            user_data['id'] = doc.id  # Agrega el ID del documento como parte del usuario
            users.append(user_data)

        print(f"Endpoint de usuarios: tiene {len(users)} documentos")
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")

    
@app.put("/users/{user_id}")
def update_user(user_id: str, user: User):
    user_ref = db.collection("users").document(user_id)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")
    user_ref.update(user.dict())
    return {"message": "User updated successfully"}

@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    user_ref = db.collection("users").document(user_id)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")
    user_ref.delete()
    return {"message": "User deleted successfully"}


# Endpoint to get users by any role
@app.get("/users/by-role/{rol}")
def get_users_by_role(rol: str):
    """
    Retorna todos los usuarios con el rol especificado.
    """
    users = [
        {"id": doc.id, **doc.to_dict()}
        for doc in db.collection("users").where("rol", "==", rol).stream()
    ]
    return users

# Endpoint to get students by grade ID
@app.get("/students/by-grado/{gradoId}")
def get_students_by_grado(gradoId: str):
    """
    Retorna todos los alumnos que pertenecen al grado especificado.
    """
    students = [
        {"id": doc.id, **doc.to_dict()}
        for doc in db.collection("students").where("gradoId", "==", gradoId).stream()
    ]
    return students

# Endpoint to get students by shift (turno)
@app.get("/students/by-turno/{turno}")
def get_students_by_turno(turno: str):
    """
    Retorna todos los alumnos con el turno especificado ('matutino' o 'vespertino').
    """
    students = [
        {"id": doc.id, **doc.to_dict()}
        for doc in db.collection("students").where("turno", "==", turno).stream()
    ]
    return students

# Endpoint to get available options for tutor-student relations
@app.get("/relations/available-options")
def get_available_options():
    # Fetch students
    students = [
        {
            "id": doc.id,
            "nombreCompleto": f"{doc.to_dict().get('nombre', '')} {doc.to_dict().get('apellido', '')}",
            "gradoId": doc.to_dict().get("gradoId")
        }
        for doc in db.collection("students").stream()
    ]

    # Fetch tutors
    tutors = [
        {
            "id": doc.id,
            "nombre": doc.to_dict().get("nombre"),
            "email": doc.to_dict().get("email"),
            "fotoPerfilUrl": doc.to_dict().get("fotoPerfilUrl")
        }
        for doc in db.collection("users").where("rol", "==", "tutor").stream()
    ]

    return {"students": students, "tutors": tutors}

# Endpoint to get detailed tutor-student relations
@app.get("/relations/detailed")
def get_detailed_relations():
    relations = []
    tutor_student_relations = db.collection("tutor_student_relations").stream()

    for relation in tutor_student_relations:
        relation_data = relation.to_dict()
        tutor = db.collection("users").document(relation_data["tutorId"]).get().to_dict()
        student = db.collection("students").document(relation_data["alumnoId"]).get().to_dict()

        relations.append({
            "relationId": relation.id,
            "tutor": {"nombre": tutor["nombre"], "email": tutor["email"]},
            "student": {"nombre": student["nombre"], "apellido": student["apellido"], "gradoId": student["gradoId"]}
        })

    return relations

# Improved POST endpoint for tutor-student relations
@app.post("/tutor-student")
def create_tutor_student_relation(relation: TutorStudentRelation):
    # Check for existing relation
    existing_relation = db.collection("tutor_student_relations").where("tutorId", "==", relation.tutorId).where("alumnoId", "==", relation.alumnoId).get()
    if existing_relation:
        raise HTTPException(status_code=400, detail="Relation already exists")

    # Create new relation
    relation_ref = db.collection("tutor_student_relations").add(relation.dict())
    return {"id": relation_ref[1].id, "message": "Relation created successfully"}

@app.get("/tutor-student")
def get_tutor_student_relations():
    relations = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("tutor_student_relations").stream()
    ]
    return relations

@app.get("/tutor-student/{relation_id}")
def get_tutor_student_relation(relation_id: str):
    relation = db.collection("tutor_student_relations").document(relation_id).get()
    if not relation.exists:
        raise HTTPException(status_code=404, detail="Relation not found")
    return relation.to_dict()

@app.put("/tutor-student/{relation_id}")
def update_tutor_student_relation(relation_id: str, relation: TutorStudentRelation):
    relation_ref = db.collection("tutor_student_relations").document(relation_id)
    if not relation_ref.get().exists:
        raise HTTPException(status_code=404, detail="Relation not found")
    relation_ref.update(relation.dict())
    return {"message": "Relation updated successfully"}

@app.delete("/tutor-student/{relation_id}")
def delete_tutor_student_relation(relation_id: str):
    relation_ref = db.collection("tutor_student_relations").document(relation_id)
    if not relation_ref.get().exists:
        raise HTTPException(status_code=404, detail="Relation not found")
    relation_ref.delete()
    return {"message": "Relation deleted successfully"}

# CRUD for Grades
@app.post("/grades")
def create_grade(grade: Grade):
    grade_ref = db.collection("grades").add(grade.dict())
    return {"id": grade_ref[1].id, "message": "Grade created successfully"}

@app.get("/grades")
def get_grades():
    grades = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("grades").stream()
    ]
    return grades

@app.get("/grades/{grade_id}")
def get_grade(grade_id: str):
    grade = db.collection("grades").document(grade_id).get()
    if not grade.exists:
        raise HTTPException(status_code=404, detail="Grade not found")
    return grade.to_dict()

@app.put("/grades/{grade_id}")
def update_grade(grade_id: str, grade: Grade):
    grade_ref = db.collection("grades").document(grade_id)
    if not grade_ref.get().exists:
        raise HTTPException(status_code=404, detail="Grade not found")
    grade_ref.update(grade.dict())
    return {"message": "Grade updated successfully"}

@app.delete("/grades/{grade_id}")
def delete_grade(grade_id: str):
    grade_ref = db.collection("grades").document(grade_id)
    if not grade_ref.get().exists:
        raise HTTPException(status_code=404, detail="Grade not found")
    grade_ref.delete()
    return {"message": "Grade deleted successfully"}

# CRUD for Subjects
@app.post("/subjects")
def create_subject(subject: Subject):
    subject_ref = db.collection("subjects").add(subject.dict())
    return {"id": subject_ref[1].id, "message": "Subject created successfully"}

@app.get("/subjects")
def get_subjects():
    subjects = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("subjects").stream()
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

# Endpoint to create multiple relations between a grade and subjects
@app.post("/grade-subjects")
def create_grade_subject_relations(relations: List[GradeSubjectRelation]):
    created_relations = []
    for relation in relations:
        # Check for existing relation
        existing_relation = db.collection("grade_subjects").where("gradoId", "==", relation.gradoId).where("materiaId", "==", relation.materiaId).where("semestre", "==", relation.semestre).get()
        if existing_relation:
            continue  # Skip if relation already exists

        # Create new relation
        relation_ref = db.collection("grade_subjects").add(relation.dict())
        created_relations.append({"id": relation_ref[1].id, **relation.dict()})

    return {"created_relations": created_relations}

# Endpoint to get all subjects associated with a grade
@app.get("/grade-subjects/{gradoId}")
def get_grade_subjects(gradoId: str):
    subjects = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("grade_subjects").where("gradoId", "==", gradoId).stream()
    ]
    return subjects

@app.get("/grade-subjects")
def get_all_grade_subject_relations():
    """
    Retorna todas las relaciones entre grados y materias.
    """
    relations = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("grade_subjects").stream()
    ]
    return relations

@app.get("/grade-subjects/all-relations")
def get_all_grade_subjects_relations():
    """
    Retorna todas las relaciones entre grados y materias con sus IDs.
    """
    relations = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("grade_subjects").stream()
    ]
    return relations

# Endpoint to assign a professor to a subject of a grade
@app.post("/professor-subjects")
def create_professor_subject_relation(relation: ProfessorSubjectRelation):
    # Check for existing relation
    existing_relation = db.collection("professor_subjects").where("profesorId", "==", relation.profesorId).where("materiaGradoId", "==", relation.materiaGradoId).where("turno", "==", relation.turno).where("anioEscolar", "==", relation.anioEscolar).get()
    if existing_relation:
        raise HTTPException(status_code=400, detail="Relation already exists")

    # Create new relation
    relation_ref = db.collection("professor_subjects").add(relation.dict())
    return {"id": relation_ref[1].id, "message": "Relation created successfully"}

@app.get("/professor-subjects")
def get_all_professor_subject_relations():
    """
    Retorna todas las relaciones entre profesores y materias.
    """
    relations = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("professor_subjects").stream()
    ]
    return relations

# Endpoint to list all subject assignments for a professor
@app.get("/professor-subjects/{profesorId}")
def get_professor_subjects(profesorId: str):
    assignments = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("professor_subjects").where("profesorId", "==", profesorId).stream()
    ]
    return assignments

# Endpoint to get all students in a grade for a specific subject
@app.get("/professor-subjects/{materiaGradoId}/students")
def get_students_in_subject(materiaGradoId: str):
    # Fetch the grade ID from the grade-subject relation
    grade_subject = db.collection("grade_subjects").document(materiaGradoId).get()
    if not grade_subject.exists:
        raise HTTPException(status_code=404, detail="Grade-Subject relation not found")

    gradoId = grade_subject.to_dict()["gradoId"]

    # Fetch students in the grade
    students = [
        {"id": doc.id, **doc.to_dict()} for doc in db.collection("students").where("gradoId", "==", gradoId).stream()
    ]
    return students

# Endpoint to get user-related information
@app.get("/user/{user_id}/info")
def get_user_info(user_id: str):
    user_data = db.collection("users").document(user_id).get()
    if not user_data.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_info = user_data.to_dict()
    rol = user_info.get("rol")

    # Si es tutor, obtenemos información de hijos y notificaciones
    if rol == "tutor":
        tutor_students = db.collection("tutor_student_relations").where("tutorId", "==", user_id).stream()
        grades = []
        subjects = []
        for relation in tutor_students:
            student_id = relation.to_dict()["alumnoId"]
            student = db.collection("students").document(student_id).get().to_dict()
            grades.append(student["gradoId"])
            grade_subjects = db.collection("grade_subjects").where("gradoId", "==", student["gradoId"]).stream()
            for subject in grade_subjects:
                subjects.append(subject.to_dict()["materiaId"])
        notifications = [
            {"id": doc.id, **doc.to_dict()} for doc in db.collection("notifications").where("tutorId", "==", user_id).stream()
        ]
        return {
            "user": user_info,
            "grades": grades,
            "subjects": subjects,
            "notifications": notifications,
        }

    # Si es profesor, mostramos materias y grados asignados
    if rol == "profesor":
        assigned_subjects = db.collection("professor_subjects").where("profesorId", "==", user_id).stream()
        grades = []
        subjects = []
        for relation in assigned_subjects:
            subject_data = relation.to_dict()
            subjects.append(subject_data["materiaId"])
            grades.append(subject_data["gradoId"])
        return {
            "user": user_info,
            "grades": grades,
            "subjects": subjects,
        }

    # Para cualquier otro rol, solo devolvemos la info del usuario
    return {
        "user": user_info
    }


# Endpoint to mark attendance and generate notifications
@app.post("/attendance/mark")
def mark_attendance(attendance: Attendance):
    # Validar que la materia exista
    subject_doc = db.collection("subjects").document(attendance.materiaId).get()
    if not subject_doc.exists:
        raise HTTPException(status_code=404, detail="Subject (materia) not found")

    # Guardar la asistencia
    db.collection("attendance").add(attendance.dict())

    # Obtener el nombre de la materia
    nombre_materia = subject_doc.to_dict().get("nombre", "una materia")

    # Buscar relaciones tutor-alumno para enviar notificación
    tutor_relations = db.collection("tutor_student_relations").where("alumnoId", "==", attendance.alumnoId).stream()
    
    # Enviar notificación a cada tutor relacionado
    for relation in tutor_relations:
        tutor_id = relation.to_dict()["tutorId"]
        notification = Notification(
            alumnoId=attendance.alumnoId,
            tutorId=tutor_id,
            mensaje=f"Tu hijo/a estuvo {attendance.estado} en la clase de {nombre_materia}",
            tipo=attendance.estado,
            fechaEnvio=datetime.utcnow(),
            leido=False
        )
        db.collection("notifications").add(notification.dict())

    return {"message": "Attendance recorded successfully"}

@app.get("/attendance/summary")
def get_attendance_summary():
    try:
        attendance_docs = db.collection("attendance").stream()
        summary = []

        for doc in attendance_docs:
            att = doc.to_dict()

            # Obtener datos del alumno
            student_ref = db.collection("students").document(att["alumnoId"]).get()
            student = student_ref.to_dict() if student_ref.exists else {}

            # Obtener datos de la materia
            subject_ref = db.collection("subjects").document(att["materiaId"]).get()
            subject = subject_ref.to_dict() if subject_ref.exists else {}

            summary.append({
                "id": doc.id,
                "alumnoId": att["alumnoId"],
                "nombreAlumno": f"{student.get('nombre', '')} {student.get('apellido', '')}",
                "gradoId": student.get("gradoId", ""),
                "materiaId": att["materiaId"],
                "nombreMateria": subject.get("nombre", ""),
                "estado": att["estado"],  # presente, ausente, justificado
                "fecha": att["fecha"],
                "justificacion": att.get("justificacion", None)
            })

        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching attendance summary: {str(e)}")


@app.get("/notifications")
def get_all_notifications():
    try:
        notifications = [
            {"id": doc.id, **doc.to_dict()}
            for doc in db.collection("notifications").stream()
        ]
        print(f"Endpoint de notificaciones: tiene {len(notifications)} documentos")
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notifications: {str(e)}")


@app.get("/students/paginated")
def get_students_paginated(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    start = time.time()
    students_ref = db.collection("students")
    students_query = students_ref.offset((page - 1) * page_size).limit(page_size).stream()
    students = [
        {"id": doc.id, **doc.to_dict()} for doc in students_query
    ]
    elapsed = time.time() - start
    print(f"Tiempo sin paginación: 10 segundos Estudiantes | Tiempo con paginación: {elapsed:.2f} segundos")
    return {"page": page, "page_size": page_size, "students": students}

@app.get("/users/paginated")
def get_users_paginated(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    start = time.time()
    users_ref = db.collection("users")
    users_query = users_ref.offset((page - 1) * page_size).limit(page_size).stream()
    users = [
        {"id": doc.id, **doc.to_dict()} for doc in users_query
    ]
    elapsed = time.time() - start
    print(f"Traer Usuarios Tiempo sin paginación: 13 segundos | Tiempo con paginación: {elapsed:.2f} segundos")
    return {"page": page, "page_size": page_size, "users": users}

@app.get("/notifications/paginated")
def get_notifications_paginated(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    start = time.time()
    notifications_ref = db.collection("notifications")
    notifications_query = notifications_ref.offset((page - 1) * page_size).limit(page_size).stream()
    notifications = [
        {"id": doc.id, **doc.to_dict()} for doc in notifications_query
    ]
    elapsed = time.time() - start
    print(f"Tiempo sin paginación de Notificaciones: 11 segundos | Tiempo con paginación: {elapsed:.2f} segundos")
    return {"page": page, "page_size": page_size, "notifications": notifications}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
