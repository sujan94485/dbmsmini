-- =============================================================================
-- AI-Enhanced Database Query Assistant - Phase 2
-- Database Schema & Sample Dataset: college_db
-- =============================================================================

CREATE DATABASE IF NOT EXISTS college_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE college_db;

-- Drop existing tables in reverse foreign-key order for clean re-runs
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS faculty;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS query_history;

-- -----------------------------------------------------------------------------
-- 1. departments
-- -----------------------------------------------------------------------------
CREATE TABLE departments (
    department_id INT AUTO_INCREMENT PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    hod_name VARCHAR(100) NOT NULL
);

-- -----------------------------------------------------------------------------
-- 2. students
-- -----------------------------------------------------------------------------
CREATE TABLE students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    student_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    gender VARCHAR(20) NOT NULL,
    department_id INT NOT NULL,
    admission_year INT NOT NULL,
    CONSTRAINT fk_students_department
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- -----------------------------------------------------------------------------
-- 3. courses
-- -----------------------------------------------------------------------------
CREATE TABLE courses (
    course_id INT AUTO_INCREMENT PRIMARY KEY,
    course_name VARCHAR(120) NOT NULL,
    department_id INT NOT NULL,
    credits INT NOT NULL,
    CONSTRAINT fk_courses_department
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- -----------------------------------------------------------------------------
-- 4. enrollments
-- -----------------------------------------------------------------------------
CREATE TABLE enrollments (
    enrollment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    course_id INT NOT NULL,
    marks DECIMAL(5, 2) NOT NULL,
    semester INT NOT NULL,
    CONSTRAINT fk_enrollments_student
        FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_enrollments_course
        FOREIGN KEY (course_id) REFERENCES courses(course_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- 5. faculty
-- -----------------------------------------------------------------------------
CREATE TABLE faculty (
    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL,
    department_id INT NOT NULL,
    designation VARCHAR(100) NOT NULL,
    CONSTRAINT fk_faculty_department
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- -----------------------------------------------------------------------------
-- 6. query_history
-- -----------------------------------------------------------------------------
CREATE TABLE query_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    natural_language_question TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    execution_status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- Sample Data
-- =============================================================================

INSERT INTO departments (department_id, department_name, hod_name) VALUES
(1, 'Computer Science', 'Dr. Ananya Sharma'),
(2, 'Information Technology', 'Dr. Rajesh Nair'),
(3, 'Electronics & Communication', 'Dr. Meera Kulkarni'),
(4, 'Mechanical Engineering', 'Dr. Vikram Deshmukh'),
(5, 'Civil Engineering', 'Dr. Suresh Iyer');

INSERT INTO students (student_id, student_name, email, gender, department_id, admission_year) VALUES
(1, 'Aarav Mehta', 'aarav.mehta@college.edu', 'Male', 1, 2023),
(2, 'Diya Patel', 'diya.patel@college.edu', 'Female', 1, 2023),
(3, 'Rohan Verma', 'rohan.verma@college.edu', 'Male', 1, 2024),
(4, 'Sneha Reddy', 'sneha.reddy@college.edu', 'Female', 2, 2023),
(5, 'Kabir Singh', 'kabir.singh@college.edu', 'Male', 2, 2022),
(6, 'Ishita Gupta', 'ishita.gupta@college.edu', 'Female', 2, 2024),
(7, 'Aditya Joshi', 'aditya.joshi@college.edu', 'Male', 3, 2023),
(8, 'Priya Menon', 'priya.menon@college.edu', 'Female', 3, 2022),
(9, 'Karan Malhotra', 'karan.malhotra@college.edu', 'Male', 4, 2023),
(10, 'Neha Kapoor', 'neha.kapoor@college.edu', 'Female', 4, 2024),
(11, 'Siddharth Rao', 'siddharth.rao@college.edu', 'Male', 5, 2022),
(12, 'Pooja Bhat', 'pooja.bhat@college.edu', 'Female', 1, 2022);

INSERT INTO courses (course_id, course_name, department_id, credits) VALUES
(1, 'Database Management Systems', 1, 4),
(2, 'Data Structures & Algorithms', 1, 4),
(3, 'Operating Systems', 1, 3),
(4, 'Web Application Development', 2, 4),
(5, 'Computer Networks', 2, 3),
(6, 'Cloud Computing Fundamentals', 2, 3),
(7, 'Digital Signal Processing', 3, 4),
(8, 'Embedded Systems', 3, 3),
(9, 'Thermodynamics', 4, 4),
(10, 'Structural Analysis', 5, 4);

INSERT INTO enrollments (enrollment_id, student_id, course_id, marks, semester) VALUES
(1, 1, 1, 91.50, 4),
(2, 1, 2, 88.00, 3),
(3, 2, 1, 94.00, 4),
(4, 2, 3, 86.50, 5),
(5, 3, 1, 79.00, 4),
(6, 3, 2, 82.50, 3),
(7, 4, 4, 89.00, 4),
(8, 4, 1, 87.00, 4),
(9, 5, 5, 74.50, 5),
(10, 5, 6, 81.00, 6),
(11, 6, 4, 92.00, 4),
(12, 7, 7, 78.00, 4),
(13, 7, 8, 84.00, 5),
(14, 8, 7, 90.50, 4),
(15, 9, 9, 72.00, 3),
(16, 10, 9, 85.50, 3),
(17, 11, 10, 68.00, 5),
(18, 12, 1, 96.00, 4),
(19, 12, 3, 91.00, 5),
(20, 4, 5, 83.00, 5);

INSERT INTO faculty (faculty_id, faculty_name, department_id, designation) VALUES
(1, 'Dr. Ananya Sharma', 1, 'Professor & HOD'),
(2, 'Prof. Arvind Krishnan', 1, 'Associate Professor'),
(3, 'Prof. Kavita Deshpande', 1, 'Assistant Professor'),
(4, 'Dr. Rajesh Nair', 2, 'Professor & HOD'),
(5, 'Prof. Manish Tiwari', 2, 'Assistant Professor'),
(6, 'Dr. Meera Kulkarni', 3, 'Professor & HOD'),
(7, 'Dr. Vikram Deshmukh', 4, 'Professor & HOD'),
(8, 'Dr. Suresh Iyer', 5, 'Professor & HOD');

INSERT INTO query_history (history_id, natural_language_question, generated_sql, execution_status, created_at) VALUES
(1, 'Show all students who scored above 85 in Database Management Systems.', 'SELECT s.student_name, e.marks FROM students s JOIN enrollments e ON s.student_id = e.student_id JOIN courses c ON e.course_id = c.course_id WHERE c.course_name = ''Database Management Systems'' AND e.marks > 85;', 'Sample', '2026-11-26 10:00:00'),
(2, 'Count the number of students in each department.', 'SELECT d.department_name, COUNT(s.student_id) AS student_count FROM departments d LEFT JOIN students s ON d.department_id = s.department_id GROUP BY d.department_id, d.department_name;', 'Sample', '2026-11-26 10:15:00'),
(3, 'List courses ordered by credits descending.', 'SELECT course_name, credits FROM courses ORDER BY credits DESC, course_name ASC;', 'Sample', '2026-11-26 10:30:00');
