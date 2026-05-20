require "test_helper"

class ReceiptsControllerTest < ActionDispatch::IntegrationTest
  setup do
    @group = carpool_groups(:may_group)
  end

  test "redirects to login when not authenticated" do
    get carpool_group_receipt_path(@group)
    assert_redirected_to new_session_path
  end

  test "GET show returns a PDF for a group member" do
    sign_in_as(users(:alice))
    get carpool_group_receipt_path(@group)
    assert_response :success
    assert_equal "application/pdf", response.media_type
  end

  test "GET show filename contains the group name and month" do
    sign_in_as(users(:alice))
    get carpool_group_receipt_path(@group)
    disposition = response.headers["Content-Disposition"]
    assert_match "morning-commute-group", disposition
    assert_match "May_2026", disposition
  end

  test "GET show returns 404 for a non-member" do
    outsider = User.create!(uid: "uid_out3", display_name: "Out", email: "out3@example.com")
    sign_in_as(outsider)
    get carpool_group_receipt_path(@group)
    assert_response :not_found
  end
end
