require "test_helper"

class DashboardControllerTest < ActionDispatch::IntegrationTest
  test "redirects to login when not authenticated" do
    get dashboard_path
    assert_redirected_to new_session_path
  end

  test "GET index shows the user's carpool groups" do
    sign_in_as(users(:alice))
    get dashboard_path
    assert_response :success
    assert_select ".group-card", count: 1
  end

  test "GET index shows empty state when user has no groups" do
    sign_in_as(users(:bob))
    # Remove bob from his group so he has no groups
    memberships(:bob_may).destroy
    get dashboard_path
    assert_response :success
    assert_select ".empty-state"
  end
end
