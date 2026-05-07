from server.core.rbac import Role, has_role


class FakeUser:
    def __init__(self, role: str, email: str = "test@test.com"):
        self.role = role
        self.email = email
        self.id = 1


class TestRbacRoles:
    def test_admin_has_admin(self):
        assert has_role(FakeUser("admin"), Role.ADMIN)

    def test_admin_has_analyst(self):
        assert has_role(FakeUser("admin"), Role.ANALYST)

    def test_admin_has_viewer(self):
        assert has_role(FakeUser("admin"), Role.VIEWER)

    def test_analyst_has_analyst(self):
        assert has_role(FakeUser("analyst"), Role.ANALYST)

    def test_analyst_has_viewer(self):
        assert has_role(FakeUser("analyst"), Role.VIEWER)

    def test_analyst_not_admin(self):
        assert not has_role(FakeUser("analyst"), Role.ADMIN)

    def test_viewer_has_viewer(self):
        assert has_role(FakeUser("viewer"), Role.VIEWER)

    def test_viewer_not_analyst(self):
        assert not has_role(FakeUser("viewer"), Role.ANALYST)

    def test_viewer_not_admin(self):
        assert not has_role(FakeUser("viewer"), Role.ADMIN)

    def test_unknown_role_denied(self):
        assert not has_role(FakeUser("guest"), Role.VIEWER)

    def test_role_enum_values(self):
        assert Role.ADMIN == "admin"
        assert Role.ANALYST == "analyst"
        assert Role.VIEWER == "viewer"
