import os
import shutil
import pytest
from fastapi.testclient import TestClient
from sutra.web.app import app

client = TestClient(app)

@pytest.fixture
def dummy_docx_file(tmp_path):
    # Copy project's test_manuscript.docx to tmp path to test real file uploads
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_docx = os.path.join(base_dir, "test_manuscript.docx")
    dest_docx = tmp_path / "test_manuscript.docx"
    shutil.copy2(src_docx, dest_docx)
    return str(dest_docx)

def test_web_app_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "Sutra Press" in response.text
    assert 'id="uploadForm"' in response.text
    assert 'id="dropZone"' in response.text
    assert 'id="progressCard"' in response.text
    assert 'id="resultsCard"' in response.text

def test_web_app_conversion_flow(dummy_docx_file):
    # Upload docx to endpoint
    with open(dummy_docx_file, "rb") as f:
        response = client.post(
            "/convert",
            files={"file": ("test_manuscript.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"layout": "single"}
        )
        
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "slug" in data
    assert data["filename"] == "test_manuscript.docx"
    assert "triage" in data
    assert data["triage"]["verdict"] == "pass"
    assert "xml_validation" in data
    assert data["xml_validation"]["passed"] is True
    assert "compile" in data
    assert data["compile"]["passed"] is True
    
    slug = data["slug"]
    
    # 1. Verify ZIP package download
    response_zip = client.get(f"/download/{slug}/zip")
    assert response_zip.status_code == 200
    assert response_zip.headers["content-type"] == "application/zip"
    
    # 2. Verify PDF download
    response_pdf = client.get(f"/download/{slug}/pdf")
    assert response_pdf.status_code == 200
    assert response_pdf.headers["content-type"] == "application/pdf"
    
    # 3. Verify XML download
    response_xml = client.get(f"/download/{slug}/xml")
    assert response_xml.status_code == 200
    assert response_xml.headers["content-type"] == "application/xml"
    
    # 4. Verify TEX download
    response_tex = client.get(f"/download/{slug}/tex")
    assert response_tex.status_code == 200
    assert "text/plain" in response_tex.headers["content-type"]
    
    # 5. Verify PDF preview endpoint
    response_preview = client.get(f"/preview/{slug}/pdf")
    assert response_preview.status_code == 200
    assert response_preview.headers["content-type"] == "application/pdf"

def test_web_app_conversion_invalid_extension():
    response = client.post(
        "/convert",
        files={"file": ("test.txt", b"dummy content", "text/plain")},
        data={"layout": "single"}
    )
    assert response.status_code == 400
    assert "Only Word Document" in response.json()["detail"]

def test_web_app_downloads_not_found():
    response = client.get("/download/invalid-slug/pdf")
    assert response.status_code == 404
    assert "Package not found" in response.json()["detail"]


def test_project_workflow(dummy_docx_file):
    # 1. Upload manuscript
    with open(dummy_docx_file, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("test_manuscript.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert response.status_code == 200
    project_data = response.json()
    project_id = project_data["id"]
    assert "blocks" in project_data
    assert len(project_data["blocks"]) > 0

    # Verify that the project is listed in GET /projects
    response_list = client.get("/projects")
    assert response_list.status_code == 200
    projects_list = response_list.json()
    assert any(p["id"] == project_id for p in projects_list)

    # 2. Verify files are encrypted at rest
    from sutra.web.app import build_root
    project_dir = os.path.join(build_root, "projects", project_id)
    docx_path = os.path.join(project_dir, "manuscript.docx.enc")
    state_path = os.path.join(project_dir, "project_state.json.enc")
    assert os.path.exists(docx_path)
    assert os.path.exists(state_path)
    
    # Check that they cannot be read as raw ZIP or JSON
    with open(docx_path, "rb") as f:
        content = f.read()
        assert not content.startswith(b"PK") # DOCX/ZIP signature
    with open(state_path, "rb") as f:
        content = f.read()
        assert not content.startswith(b"{") # JSON signature

    # 3. Retrieve project blocks
    response_get = client.get(f"/project/{project_id}")
    assert response_get.status_code == 200
    assert response_get.json()["id"] == project_id

    # 4. Gated Compile check: Add an unresolved unrecognized block and verify generate is blocked (400)
    blocks = project_data["blocks"]
    unrecognized_block = {
        "id": "unrecognized-test-block",
        "type": "unrecognized",
        "content": {"raw_type": "Para", "content_text": "unclassified text content"},
        "state": "unrecognized",
        "warnings": ["Low confidence"],
        "is_flagged_manual": False
    }
    blocks.append(unrecognized_block)
    
    response_update = client.post(
        f"/project/{project_id}/update",
        json={"blocks": blocks}
    )
    assert response_update.status_code == 200
    
    # Try generate - should fail with 400 because of unresolved unrecognized block
    response_gen_fail = client.post(
        f"/project/{project_id}/generate",
        data={"layout": "single"}
    )
    assert response_gen_fail.status_code == 400
    assert "Generation is gated" in response_gen_fail.json()["detail"]

    # 5. Resolve unrecognized block by flagging it for manual handling
    blocks[-1]["is_flagged_manual"] = True
    client.post(
        f"/project/{project_id}/update",
        json={"blocks": blocks}
    )
    
    # Try generate again - should succeed!
    response_gen_success = client.post(
        f"/project/{project_id}/generate",
        data={"layout": "single"}
    )
    assert response_gen_success.status_code == 200
    gen_data = response_gen_success.json()
    assert gen_data["success"] is True
    run_id = gen_data["run_id"]

    # 6. Verify downloads
    res_pdf = client.get(f"/project/{project_id}/download/{run_id}/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"

    res_xml = client.get(f"/project/{project_id}/download/{run_id}/xml")
    assert res_xml.status_code == 200
    assert res_xml.headers["content-type"] == "application/xml"

    res_log = client.get(f"/project/{project_id}/download/{run_id}/log")
    assert res_log.status_code == 200
    assert "Review Session Log" in res_log.text

    # 7. Delete project
    response_del = client.delete(f"/project/{project_id}")
    assert response_del.status_code == 200
    assert not os.path.exists(project_dir)


def test_login_success():
    response = client.post("/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "Admin"


def test_login_invalid():
    response = client.post("/login", json={"username": "admin", "password": "wrongpassword"})
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_admin_users_crud():
    # 1. Get initial users
    response_get = client.get("/admin/users")
    assert response_get.status_code == 200
    users = response_get.json()
    assert len(users) >= 2
    
    # 2. Create user
    new_user_data = {
        "username": "testuser",
        "email": "test@sutra.press",
        "password": "testpassword",
        "role": "Editor",
        "plan_id": "free",
        "status": "Active"
    }
    response_create = client.post("/admin/users", json=new_user_data)
    assert response_create.status_code == 200
    created_user = response_create.json()
    assert created_user["username"] == "testuser"
    assert created_user["email"] == "test@sutra.press"
    assert "id" in created_user
    user_id = created_user["id"]
    
    # 3. Create user duplicate username check
    response_dup = client.post("/admin/users", json=new_user_data)
    assert response_dup.status_code == 400
    assert "Username already exists" in response_dup.json()["detail"]
    
    # 4. Update user
    update_data = {
        "username": "updateduser",
        "email": "updated@sutra.press",
        "role": "Editor",
        "plan_id": "professional",
        "status": "Active"
    }
    response_update = client.put(f"/admin/users/{user_id}", json=update_data)
    assert response_update.status_code == 200
    updated_user = response_update.json()
    assert updated_user["username"] == "updateduser"
    assert updated_user["plan_id"] == "professional"
    
    # 5. Delete user
    response_delete = client.delete(f"/admin/users/{user_id}")
    assert response_delete.status_code == 200
    assert response_delete.json() == {"success": True}
    
    # 6. Verify user is deleted
    response_get_after = client.get("/admin/users")
    assert not any(u["id"] == user_id for u in response_get_after.json())


def test_admin_plans_crud():
    # 1. Get initial plans
    response_get = client.get("/admin/plans")
    assert response_get.status_code == 200
    plans = response_get.json()
    assert len(plans) >= 3
    
    # 2. Create plan
    new_plan_data = {
        "name": "Custom Test Plan",
        "price": "$50 / month",
        "limit": "50 uploads / month",
        "features": ["Feature A", "Feature B"]
    }
    response_create = client.post("/admin/plans", json=new_plan_data)
    assert response_create.status_code == 200
    created_plan = response_create.json()
    assert created_plan["name"] == "Custom Test Plan"
    assert "id" in created_plan
    plan_id = created_plan["id"]
    
    # 3. Update plan
    update_data = {
        "name": "Updated Custom Plan",
        "price": "$60 / month",
        "limit": "60 uploads / month",
        "features": ["Feature A", "Feature B", "Feature C"]
    }
    response_update = client.put(f"/admin/plans/{plan_id}", json=update_data)
    assert response_update.status_code == 200
    updated_plan = response_update.json()
    assert updated_plan["name"] == "Updated Custom Plan"
    assert updated_plan["price"] == "$60 / month"
    
    # 4. Delete plan
    response_delete = client.delete(f"/admin/plans/{plan_id}")
    assert response_delete.status_code == 200
    assert response_delete.json() == {"success": True}
    
    # 5. Verify plan is deleted
    response_get_after = client.get("/admin/plans")
    assert not any(p["id"] == plan_id for p in response_get_after.json())


def test_delete_last_admin_prevented():
    response_get = client.get("/admin/users")
    users = response_get.json()
    admin_id = next(u["id"] for u in users if u["username"] == "admin")
    
    response_del = client.delete(f"/admin/users/{admin_id}")
    assert response_del.status_code == 400
    assert "Cannot delete the last admin user" in response_del.json()["detail"]


@pytest.fixture
def dummy_pdf_file(tmp_path):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_pdf = os.path.join(base_dir, "build", "test_manuscript", "article.pdf")
    if not os.path.exists(src_pdf):
        for root, dirs, files in os.walk(os.path.join(base_dir, "build")):
            for f in files:
                if f.endswith(".pdf"):
                    src_pdf = os.path.join(root, f)
                    break
            if os.path.exists(src_pdf):
                break
    dest_pdf = tmp_path / "article.pdf"
    shutil.copy2(src_pdf, dest_pdf)
    return str(dest_pdf)


def test_journal_profiles_flow(dummy_pdf_file):
    # 1. Analyze PDF
    with open(dummy_pdf_file, "rb") as f:
        response = client.post(
            "/journals/analyze",
            files={"file": ("article.pdf", f, "application/pdf")},
            data={"journal_id": "testjournal", "journal_name": "Test Journal"}
        )
    assert response.status_code == 200
    settings = response.json()
    assert settings["journal_id"] == "testjournal"
    assert settings["journal_name"] == "Test Journal"
    assert "paper_size" in settings["page"]
    assert "columns" in settings["page"]
    
    # 2. Save profile
    response_save = client.post("/journals", json=settings)
    assert response_save.status_code == 200
    assert response_save.json()["success"] is True
    
    # 3. List profiles
    response_list = client.get("/journals")
    assert response_list.status_code == 200
    profiles = response_list.json()
    assert any(p["journal_id"] == "testjournal" for p in profiles)
    
    # 4. Get single profile
    response_get = client.get("/journals/testjournal")
    assert response_get.status_code == 200
    assert response_get.json()["journal_name"] == "Test Journal"
    
    # 5. Delete profile
    response_del = client.delete("/journals/testjournal")
    assert response_del.status_code == 200
    assert response_del.json()["success"] is True
    
    # Verify deleted
    response_get_deleted = client.get("/journals/testjournal")
    assert response_get_deleted.status_code == 404


def test_project_review_edit_flow(dummy_docx_file):
    # 1. Upload manuscript
    with open(dummy_docx_file, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("test_manuscript.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert response.status_code == 200
    project_data = response.json()
    project_id = project_data["id"]
    blocks = project_data["blocks"]
    
    # Modify the content of the first non-empty text block
    assert len(blocks) > 0
    test_block = None
    for b in blocks:
        if isinstance(b["content"], list) and len(b["content"]) > 0 and "text" in b["content"][0]:
            test_block = b
            break
    assert test_block is not None
    original_text = test_block["content"][0]["text"]
    
    modified_text = "Modified by output review integration test"
    test_block["content"] = [{"text": modified_text, "bold": False, "italic": False}]
    test_block["state"] = "confirmed"
    
    # 2. Call review-edit endpoint
    response_edit = client.post(
        f"/project/{project_id}/review-edit",
        json={
            "blocks": blocks,
            "layout": "single",
            "journal_id": "generic"
        }
    )
    assert response_edit.status_code == 200
    res_data = response_edit.json()
    assert res_data["success"] is True
    assert "run_id" in res_data
    run_id = res_data["run_id"]
    
    # 3. Retrieve project and verify updated block content
    response_get = client.get(f"/project/{project_id}")
    assert response_get.status_code == 200
    updated_project = response_get.json()
    updated_blocks = updated_project["blocks"]
    updated_block = next(b for b in updated_blocks if b["id"] == test_block["id"])
    updated_text = updated_block["content"][0]["text"]
    assert updated_text == modified_text
    
    # 4. Check PDF download succeeds
    res_pdf = client.get(f"/project/{project_id}/download/{run_id}/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    
    # 5. Clean up project
    response_del = client.delete(f"/project/{project_id}")
    assert response_del.status_code == 200


def test_ai_identify_endpoint(dummy_docx_file):
    # 1. Upload manuscript
    with open(dummy_docx_file, "rb") as f:
        response_upload = client.post(
            "/upload",
            files={"file": ("test_manuscript.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert response_upload.status_code == 200
    project_id = response_upload.json()["id"]

    try:
        # 2. Call AI Identify endpoint
        response_ai = client.post(f"/project/{project_id}/ai-identify", json={})
        assert response_ai.status_code == 200
        ai_data = response_ai.json()
        assert ai_data["success"] is True
        assert "provider" in ai_data
        assert "updated_count" in ai_data
        assert "message" in ai_data

        # 3. Verify project state updated and log recorded
        response_get = client.get(f"/project/{project_id}")
        assert response_get.status_code == 200
        proj = response_get.json()
        assert any("AI Block Identification" in log for log in proj.get("logs", []))
    finally:
        # 4. Clean up
        client.delete(f"/project/{project_id}")



