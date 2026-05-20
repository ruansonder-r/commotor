require "test_helper"

class TripLogTest < ActiveSupport::TestCase
  setup do
    @group = carpool_groups(:may_group)
    @user  = users(:alice)
  end

  test "valid with group and recorded_by" do
    log = TripLog.new(carpool_group: @group, recorded_by: @user)
    assert log.valid?
  end

  test "defaults occurred_at to now when blank" do
    log = TripLog.new(carpool_group: @group, recorded_by: @user)
    log.valid?
    assert_not_nil log.occurred_at
  end

  test "defaults trip_count to 1 when blank" do
    log = TripLog.new(carpool_group: @group, recorded_by: @user)
    log.valid?
    assert_equal 1, log.trip_count
  end

  test "trip_count must be a positive integer" do
    log = TripLog.new(carpool_group: @group, recorded_by: @user, trip_count: 0)
    assert_not log.valid?
    assert_includes log.errors[:trip_count], "must be greater than 0"
  end

  test "trip_count cannot be a decimal" do
    log = TripLog.new(carpool_group: @group, recorded_by: @user, trip_count: 1.5)
    assert_not log.valid?
    assert_includes log.errors[:trip_count], "must be an integer"
  end

  test "cannot be created when group splits do not sum to 1.0" do
    incomplete_group = CarpoolGroup.create!(name: "Incomplete", month: Date.new(2026, 6, 1),
                                            car: cars(:corolla), trip: trips(:commute))
    Membership.create!(user: @user, carpool_group: incomplete_group, cost_split_percentage: 0.50)

    log = TripLog.new(carpool_group: incomplete_group, recorded_by: @user)
    assert_not log.valid?
    assert_includes log.errors[:base], "cannot log a trip until all membership splits sum to 100%"
  end

  test "records the user who tapped the + button" do
    assert_equal users(:alice), trip_logs(:log_one).recorded_by
  end
end
