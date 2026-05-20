require "test_helper"

class TripLogsControllerTest < ActionDispatch::IntegrationTest
  setup do
    @group = carpool_groups(:may_group)
    sign_in_as(users(:alice))
  end

  test "POST create responds with turbo stream on success" do
    assert_difference "@group.trip_logs.count", 1 do
      post carpool_group_trip_logs_path(@group),
           headers: { "Accept" => "text/vnd.turbo-stream.html" }
    end
    assert_response :success
    assert_equal "text/vnd.turbo-stream.html", response.media_type
  end

  test "POST create falls back to redirect without turbo stream header" do
    assert_difference "@group.trip_logs.count", 1 do
      post carpool_group_trip_logs_path(@group)
    end
    assert_redirected_to carpool_group_path(@group)
  end

  test "POST create sets recorded_by to current user" do
    post carpool_group_trip_logs_path(@group),
         headers: { "Accept" => "text/vnd.turbo-stream.html" }
    assert_equal users(:alice), @group.trip_logs.order(:created_at).last.recorded_by
  end

  test "POST create returns 404 for a non-member group" do
    outsider = User.create!(uid: "uid_out2", display_name: "Out", email: "out2@example.com")
    sign_in_as(outsider)
    post carpool_group_trip_logs_path(@group)
    assert_response :not_found
  end
end
