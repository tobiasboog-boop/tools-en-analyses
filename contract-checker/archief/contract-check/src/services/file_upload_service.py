"""
File Upload Service - Handle contract file uploads to database
"""
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO

from sqlalchemy.orm import Session
from sqlalchemy import text


# Allowed file types
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx'}
ALLOWED_MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}

# Max file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


class FileUploadError(Exception):
    """Custom exception for file upload errors"""
    pass


def validate_file(filename: str, file_size: int) -> None:
    """
    Validate file before upload.

    Args:
        filename: Name of the file
        file_size: Size of file in bytes

    Raises:
        FileUploadError: If validation fails
    """
    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileUploadError(
            f"Ongeldig bestandstype: {ext}. "
            f"Alleen {', '.join(ALLOWED_EXTENSIONS)} zijn toegestaan."
        )

    # Check file size
    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        raise FileUploadError(
            f"Bestand te groot: {size_mb:.1f}MB. "
            f"Maximum is {max_mb:.0f}MB."
        )


def calculate_checksum(file_content: bytes) -> str:
    """
    Calculate SHA256 checksum of file content.

    Args:
        file_content: Binary file content

    Returns:
        Hex string of SHA256 checksum
    """
    return hashlib.sha256(file_content).hexdigest()


def check_duplicate(db: Session, checksum: str) -> Optional[int]:
    """
    Check if file with same checksum already exists.

    Args:
        db: Database session
        checksum: SHA256 checksum

    Returns:
        file_id if duplicate found, None otherwise
    """
    result = db.execute(
        text("""
            SELECT id FROM contract_checker.contract_files
            WHERE checksum = :checksum AND active = true
        """),
        {"checksum": checksum}
    )
    row = result.fetchone()
    return row[0] if row else None


def upload_file(
    db: Session,
    filename: str,
    file_content: bytes,
    uploaded_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload contract file to database.

    Args:
        db: Database session
        filename: Original filename
        file_content: Binary file content
        uploaded_by: Username of uploader

    Returns:
        Dict with upload result: {
            'file_id': int,
            'filename': str,
            'file_size': int,
            'checksum': str,
            'is_duplicate': bool,
            'duplicate_of': Optional[int]
        }

    Raises:
        FileUploadError: If validation fails
    """
    # Validate
    file_size = len(file_content)
    validate_file(filename, file_size)

    # Calculate checksum
    checksum = calculate_checksum(file_content)

    # Check for duplicate
    existing_file_id = check_duplicate(db, checksum)
    if existing_file_id:
        return {
            'file_id': existing_file_id,
            'filename': filename,
            'file_size': file_size,
            'checksum': checksum,
            'is_duplicate': True,
            'duplicate_of': existing_file_id
        }

    # Determine mime type
    ext = Path(filename).suffix.lower()
    mime_type = ALLOWED_MIME_TYPES.get(ext, 'application/octet-stream')

    # Insert into database
    result = db.execute(
        text("""
            INSERT INTO contract_checker.contract_files
            (filename, file_content, file_size, mime_type, checksum, uploaded_by)
            VALUES (:filename, :file_content, :file_size, :mime_type, :checksum, :uploaded_by)
            RETURNING id
        """),
        {
            'filename': filename,
            'file_content': file_content,
            'file_size': file_size,
            'mime_type': mime_type,
            'checksum': checksum,
            'uploaded_by': uploaded_by or 'system'
        }
    )
    db.commit()

    file_id = result.fetchone()[0]

    return {
        'file_id': file_id,
        'filename': filename,
        'file_size': file_size,
        'checksum': checksum,
        'is_duplicate': False,
        'duplicate_of': None
    }


def get_file_content(db: Session, file_id: int) -> Optional[bytes]:
    """
    Retrieve file content from database.

    Args:
        db: Database session
        file_id: File ID

    Returns:
        Binary file content or None if not found
    """
    result = db.execute(
        text("""
            SELECT file_content FROM contract_checker.contract_files
            WHERE id = :file_id AND active = true
        """),
        {'file_id': file_id}
    )
    row = result.fetchone()
    return row[0] if row else None


def get_file_info(db: Session, file_id: int) -> Optional[Dict[str, Any]]:
    """
    Get file metadata.

    Args:
        db: Database session
        file_id: File ID

    Returns:
        Dict with file info or None if not found
    """
    result = db.execute(
        text("""
            SELECT id, filename, file_size, mime_type, checksum,
                   uploaded_at, uploaded_by, last_processed_at
            FROM contract_checker.contract_files
            WHERE id = :file_id AND active = true
        """),
        {'file_id': file_id}
    )
    row = result.fetchone()

    if not row:
        return None

    return {
        'file_id': row[0],
        'filename': row[1],
        'file_size': row[2],
        'mime_type': row[3],
        'checksum': row[4],
        'uploaded_at': row[5],
        'uploaded_by': row[6],
        'last_processed_at': row[7]
    }


def mark_file_processed(db: Session, file_id: int) -> None:
    """
    Mark file as processed.

    Args:
        db: Database session
        file_id: File ID
    """
    db.execute(
        text("""
            UPDATE contract_checker.contract_files
            SET last_processed_at = NOW()
            WHERE id = :file_id
        """),
        {'file_id': file_id}
    )
    db.commit()


def delete_file(db: Session, file_id: int) -> None:
    """
    Soft delete a file (sets active=false).

    Args:
        db: Database session
        file_id: File ID
    """
    db.execute(
        text("""
            UPDATE contract_checker.contract_files
            SET active = false, deleted_at = NOW()
            WHERE id = :file_id
        """),
        {'file_id': file_id}
    )
    db.commit()
