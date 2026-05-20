require "test_helper"

class CarpoolGroupsControllerTest < ActionDispatch::IntegrationTest
  setup do
    @group = carpool_groups(:may_group)
  end

  test "redirects to login when not authenticated" do
    get carpool_group_path(@group)
    assert_redirected_to new_session_path
  end

  test "GET show renders the group detail for a member" do
    sign_in_as(users(:alice))
    get carpool_group_path(@group)
    assert_response :success
    assert_select ".group-detail"
    assert_select ".tally"
    assert_select ".members-table"
  end

  test "GET show returns 404 for a non-member" do
    outsider = User.create!(uid: "uid_outsider", display_name: "Outsider", email: "out@example.com")
    sign_in_as(outsider)
    get carpool_group_path(@group)
    assert_response :not_found
  end
end
