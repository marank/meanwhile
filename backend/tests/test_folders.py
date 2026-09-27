def test_create_list_and_delete_folder(user_factory, login):
    user_factory("folder-owner@example.com")
    auth = login("folder-owner@example.com")

    r = auth.post("/api/folders", json={"name": "Work"})
    assert r.status_code == 201
    folder = r.json()
    assert folder["name"] == "Work"
    assert folder["parent_id"] is None

    r = auth.get("/api/folders")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = auth.delete(f"/api/folders/{folder['id']}")
    assert r.status_code == 204

    r = auth.get("/api/folders")
    assert r.json() == []


def test_move_folder_to_root_persists(make_calendar):
    auth, _ = make_calendar("mover@example.com", "Cal")

    parent = auth.post("/api/folders", json={"name": "Parent"}).json()
    child = auth.post(
        "/api/folders",
        json={"name": "Child", "parent_id": parent["id"]},
    ).json()
    assert child["parent_id"] == parent["id"]

    r = auth.patch(
        f"/api/folders/{child['id']}",
        json={"parent_id": None},
    )
    assert r.status_code == 200
    assert r.json()["parent_id"] is None

    r = auth.get("/api/folders")
    folders = {f["id"]: f for f in r.json()}
    assert folders[child["id"]]["parent_id"] is None


def test_move_folder_into_another_folder(make_calendar):
    auth, _ = make_calendar("nested@example.com", "Cal")

    a = auth.post("/api/folders", json={"name": "A"}).json()
    b = auth.post("/api/folders", json={"name": "B"}).json()

    r = auth.patch(
        f"/api/folders/{b['id']}",
        json={"parent_id": a["id"]},
    )
    assert r.status_code == 200
    assert r.json()["parent_id"] == a["id"]

    folders = {f["id"]: f for f in auth.get("/api/folders").json()}
    assert folders[b["id"]]["parent_id"] == a["id"]


def test_folder_cycle_is_rejected(make_calendar):
    auth, _ = make_calendar("cycle@example.com", "Cal")

    a = auth.post("/api/folders", json={"name": "A"}).json()
    b = auth.post(
        "/api/folders",
        json={"name": "B", "parent_id": a["id"]},
    ).json()

    # A -> B is a cycle
    r = auth.patch(
        f"/api/folders/{a['id']}",
        json={"parent_id": b["id"]},
    )
    assert r.status_code == 400


def test_folder_self_parent_is_rejected(make_calendar):
    auth, _ = make_calendar("self@example.com", "Cal")

    folder = auth.post("/api/folders", json={"name": "Solo"}).json()
    r = auth.patch(
        f"/api/folders/{folder['id']}",
        json={"parent_id": folder["id"]},
    )
    assert r.status_code == 400


def test_folder_move_to_other_users_folder_is_rejected(user_factory, login):
    user_factory("owner-folder@example.com")
    user_factory("intruder-folder@example.com")

    owner_client = login("owner-folder@example.com")
    intruder_client = login("intruder-folder@example.com")

    other_folder = owner_client.post("/api/folders", json={"name": "Private"}).json()
    intruder_folder = intruder_client.post(
        "/api/folders", json={"name": "Intruder"}
    ).json()

    r = intruder_client.patch(
        f"/api/folders/{intruder_folder['id']}",
        json={"parent_id": other_folder["id"]},
    )
    assert r.status_code == 404


def test_reorder_folders_via_position(make_calendar):
    auth, _ = make_calendar("reorder@example.com", "Cal")

    a = auth.post("/api/folders", json={"name": "A"}).json()
    b = auth.post("/api/folders", json={"name": "B"}).json()
    c = auth.post("/api/folders", json={"name": "C"}).json()

    # Set explicit order: C, B, A
    auth.patch(f"/api/folders/{c['id']}", json={"position": 0})
    auth.patch(f"/api/folders/{b['id']}", json={"position": 1})
    auth.patch(f"/api/folders/{a['id']}", json={"position": 2})

    r = auth.get("/api/folders")
    assert r.status_code == 200
    names = [f["name"] for f in r.json()]
    assert names == ["C", "B", "A"]


def test_delete_folder_reassigns_children(make_calendar):
    auth, _ = make_calendar("delete-reassign@example.com", "Cal")

    parent = auth.post("/api/folders", json={"name": "Parent"}).json()
    child = auth.post(
        "/api/folders",
        json={"name": "Child", "parent_id": parent["id"]},
    ).json()

    calendar = auth.post("/api/calendars", json={"name": "My Calendar", "color": "#000000"}).json()
    r = auth.patch(
        f"/api/calendars/{calendar['id']}/members/me",
        json={"folder_id": parent["id"]},
    )
    assert r.status_code == 200
    assert r.json()["folder_id"] == parent["id"]

    r = auth.delete(f"/api/folders/{parent['id']}")
    assert r.status_code == 204

    r = auth.get("/api/folders")
    assert r.status_code == 200
    folders = {f["id"]: f for f in r.json()}
    assert folders[child["id"]]["parent_id"] is None

    r = auth.get("/api/calendars")
    assert r.status_code == 200
    item = next(i for i in r.json() if i["calendar"]["id"] == calendar["id"])
    assert item["membership"]["folder_id"] is None


def test_move_calendar_into_folder_and_back_to_root(make_calendar):
    auth, _ = make_calendar("cal-move@example.com", "Cal")

    folder = auth.post("/api/folders", json={"name": "Projects"}).json()
    calendar = auth.post("/api/calendars", json={"name": "Project A", "color": "#000000"}).json()

    r = auth.patch(
        f"/api/calendars/{calendar['id']}/members/me",
        json={"folder_id": folder["id"]},
    )
    assert r.status_code == 200
    assert r.json()["folder_id"] == folder["id"]

    r = auth.patch(
        f"/api/calendars/{calendar['id']}/members/me",
        json={"folder_id": None},
    )
    assert r.status_code == 200
    assert r.json()["folder_id"] is None


def test_reorder_calendars_via_position(make_calendar):
    auth, _ = make_calendar("cal-reorder@example.com", "Cal")

    cal_a = auth.post("/api/calendars", json={"name": "A", "color": "#000000"}).json()
    cal_b = auth.post("/api/calendars", json={"name": "B", "color": "#000000"}).json()
    cal_c = auth.post("/api/calendars", json={"name": "C", "color": "#000000"}).json()

    # Set explicit order: C, B, A
    auth.patch(f"/api/calendars/{cal_c['id']}/members/me", json={"position": 0})
    auth.patch(f"/api/calendars/{cal_b['id']}/members/me", json={"position": 1})
    auth.patch(f"/api/calendars/{cal_a['id']}/members/me", json={"position": 2})

    r = auth.get("/api/calendars")
    assert r.status_code == 200
    names = [item["calendar"]["name"] for item in r.json()]
    # "Cal" from make_calendar keeps its default position 0 and sorts by name.
    assert names == ["C", "Cal", "B", "A"]


def test_batch_reorder_sidebar(make_calendar):
    auth, _ = make_calendar("batch-sidebar@example.com", "Cal")

    a = auth.post("/api/folders", json={"name": "A"}).json()
    b = auth.post("/api/folders", json={"name": "B"}).json()
    c = auth.post("/api/folders", json={"name": "C"}).json()
    cal_a = auth.post("/api/calendars", json={"name": "Cal A", "color": "#000000"}).json()
    cal_b = auth.post("/api/calendars", json={"name": "Cal B", "color": "#000000"}).json()

    r = auth.post(
        "/api/sidebar/reorder",
        json={
            "items": [
                {"type": "folder", "id": c["id"], "parent_id": None, "position": 0},
                {"type": "folder", "id": b["id"], "parent_id": None, "position": 1},
                {"type": "folder", "id": a["id"], "parent_id": None, "position": 2},
                {"type": "calendar", "id": cal_b["id"], "parent_id": a["id"], "position": 0},
                {"type": "calendar", "id": cal_a["id"], "parent_id": a["id"], "position": 1},
            ]
        },
    )
    assert r.status_code == 204

    r = auth.get("/api/folders")
    names = [f["name"] for f in r.json()]
    assert names == ["C", "B", "A"]

    r = auth.get("/api/calendars")
    items = {item["calendar"]["id"]: item["membership"] for item in r.json()}
    assert items[cal_a["id"]]["folder_id"] == a["id"]
    assert items[cal_b["id"]]["folder_id"] == a["id"]
    assert items[cal_b["id"]]["position"] == 0
    assert items[cal_a["id"]]["position"] == 1


def test_batch_reorder_sidebar_cycle_rejected(make_calendar):
    auth, _ = make_calendar("batch-sidebar-cycle@example.com", "Cal")

    a = auth.post("/api/folders", json={"name": "A"}).json()
    b = auth.post("/api/folders", json={"name": "B", "parent_id": a["id"]}).json()

    r = auth.post(
        "/api/sidebar/reorder",
        json={
            "items": [
                {"type": "folder", "id": a["id"], "parent_id": b["id"], "position": 0},
            ]
        },
    )
    assert r.status_code == 400
