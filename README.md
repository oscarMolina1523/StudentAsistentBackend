# FastAPI Firebase REST API

Este proyecto es una API RESTful construida con FastAPI que utiliza Firebase para la autenticación y Firestore como base de datos. A continuación, se documentan los endpoints disponibles, los datos necesarios para interactuar con ellos y una descripción detallada de su funcionalidad.

## Requisitos previos

- Python 3.9 o superior.
- Archivo de configuración `.env` con las siguientes variables:
  ```env
  FIREBASE_CREDENTIALS_PATH=path/to/your/firebase/credentials.json
  ```
- Dependencias instaladas:
  ```bash
  pip install fastapi uvicorn firebase-admin python-jose python-multipart requests
  ```

## Iniciar el servidor

Ejecuta el siguiente comando para iniciar el servidor:
```bash
uvicorn main:app --reload
```

La API estará disponible en `http://127.0.0.1:8000`.

## Endpoints

### 1. Autenticación

#### **Registrar usuario**
- **URL**: `/auth/register`
- **Método**: `POST`
- **Descripción**: Registra un nuevo usuario en Firebase Authentication y almacena información adicional en Firestore.
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword",
    "role": "admin" // Valores posibles: admin, professor, tutor
  }
  ```
- **Respuesta**:
  ```json
  {
    "message": "User registered successfully",
    "user_id": "<user_id>"
  }
  ```

#### **Iniciar sesión**
- **URL**: `/auth/login`
- **Método**: `POST`
- **Descripción**: Autentica un usuario utilizando Firebase Authentication y devuelve un token de acceso.
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword"
  }
  ```
- **Respuesta**:
  ```json
  {
    "idToken": "<firebase_id_token>",
    "refreshToken": "<firebase_refresh_token>",
    "expiresIn": "3600"
  }
  ```

### 2. Estudiantes

#### **Crear estudiante**
- **URL**: `/students`
- **Método**: `POST`
- **Descripción**: Crea un nuevo estudiante en Firestore.
- **Body**:
  ```json
  {
    "name": "John Doe",
    "age": 16,
    "school_year": "10th Grade"
  }
  ```
- **Respuesta**:
  ```json
  {
    "id": "<student_id>",
    "message": "Student created successfully"
  }
  ```

#### **Obtener todos los estudiantes**
- **URL**: `/students`
- **Método**: `GET`
- **Descripción**: Devuelve una lista de todos los estudiantes, incluyendo sus IDs.
- **Respuesta**:
  ```json
  [
    {
      "id": "<student_id>",
      "name": "John Doe",
      "age": 16,
      "school_year": "10th Grade"
    }
  ]
  ```

#### **Obtener un estudiante por ID**
- **URL**: `/students/{student_id}`
- **Método**: `GET`
- **Descripción**: Devuelve los detalles de un estudiante específico por su ID.
- **Respuesta**:
  ```json
  {
    "name": "John Doe",
    "age": 16,
    "school_year": "10th Grade"
  }
  ```

#### **Actualizar estudiante**
- **URL**: `/students/{student_id}`
- **Método**: `PUT`
- **Descripción**: Actualiza los detalles de un estudiante específico por su ID.
- **Body**:
  ```json
  {
    "name": "John Doe",
    "age": 17,
    "school_year": "11th Grade"
  }
  ```
- **Respuesta**:
  ```json
  {
    "message": "Student updated successfully"
  }
  ```

#### **Eliminar estudiante**
- **URL**: `/students/{student_id}`
- **Método**: `DELETE`
- **Descripción**: Elimina un estudiante específico por su ID.
- **Respuesta**:
  ```json
  {
    "message": "Student deleted successfully"
  }
  ```

### 3. Profesores

#### **Crear profesor**
- **URL**: `/professors`
- **Método**: `POST`
- **Descripción**: Crea un nuevo profesor en Firestore.
- **Body**:
  ```json
  {
    "name": "Jane Smith",
    "subject": "Mathematics"
  }
  ```
- **Respuesta**:
  ```json
  {
    "id": "<professor_id>",
    "message": "Professor created successfully"
  }
  ```

#### **Obtener todos los profesores**
- **URL**: `/professors`
- **Método**: `GET`
- **Descripción**: Devuelve una lista de todos los profesores, incluyendo sus IDs.
- **Respuesta**:
  ```json
  [
    {
      "id": "<professor_id>",
      "name": "Jane Smith",
      "subject": "Mathematics"
    }
  ]
  ```

#### **Obtener un profesor por ID**
- **URL**: `/professors/{professor_id}`
- **Método**: `GET`
- **Descripción**: Devuelve los detalles de un profesor específico por su ID.
- **Respuesta**:
  ```json
  {
    "name": "Jane Smith",
    "subject": "Mathematics"
  }
  ```

#### **Actualizar profesor**
- **URL**: `/professors/{professor_id}`
- **Método**: `PUT`
- **Descripción**: Actualiza los detalles de un profesor específico por su ID.
- **Body**:
  ```json
  {
    "name": "Jane Smith",
    "subject": "Physics"
  }
  ```
- **Respuesta**:
  ```json
  {
    "message": "Professor updated successfully"
  }
  ```

#### **Eliminar profesor**
- **URL**: `/professors/{professor_id}`
- **Método**: `DELETE`
- **Descripción**: Elimina un profesor específico por su ID.
- **Respuesta**:
  ```json
  {
    "message": "Professor deleted successfully"
  }
  ```

### 4. Asistencia

#### **Registrar asistencia**
- **URL**: `/attendance`
- **Método**: `POST`
- **Descripción**: Registra la asistencia de un estudiante para una materia específica.
- **Body**:
  ```json
  {
    "student_id": "<student_id>",
    "subject": "Mathematics",
    "status": "absent", // Valores posibles: present, absent, justified
    "reason": "Sick"
  }
  ```
- **Respuesta**:
  ```json
  {
    "message": "Attendance marked successfully"
  }
  ```

## Notas adicionales

- Usa herramientas como [Postman](https://www.postman.com/) o la documentación interactiva en `http://127.0.0.1:8000/docs` para probar los endpoints.
- Asegúrate de incluir el token de acceso en el encabezado `Authorization` para los endpoints protegidos:
  ```
  Authorization: Bearer <access_token>
  ```