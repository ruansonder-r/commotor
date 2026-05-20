require "test_helper"

class CarpoolGroupTest < ActiveSupport::TestCase
  setup do
    @group = carpool_groups(:may_group)
  end

  test "valid with all required attributes" do
    group = CarpoolGroup.new(name: "Evening Group", month: Date.new(2026, 6, 1),
                             car: cars(:corolla), trip: trips(:commute))
    assert group.valid?
  end

  test "invalid without name" do
    group = CarpoolGroup.new(month: Date.today, car: cars(:corolla), trip: trips(:commute))
    assert_not group.valid?
    assert_includes group.errors[:name], "can't be blank"
  end

  test "invalid without month" do
    group = CarpoolGroup.new(name: "Group", car: cars(:corolla), trip: trips(:commute))
    assert_not group.valid?
    assert_includes group.errors[:month], "can't be blank"
  end

  test "trip_cost multiplies car cost_per_km by trip distance_km" do
    # R2.50/km × 40km = R100
    assert_equal 100.0, @group.trip_cost
  end

  test "monthly_tally multiplies trip_cost by total trip log count" do
    # 2 logs in fixtures × R100 = R200
    assert_equal 200.0, @group.monthly_tally
  end

  test "splits_complete? returns true when memberships sum to 1.0" do
    # alice 0.30 + bob 0.40 + carol 0.30 = 1.0
    assert @group.splits_complete?
  end

  test "splits_complete? returns false when memberships do not sum to 1.0" do
    group = CarpoolGroup.create!(name: "Partial", month: Date.new(2026, 6, 1),
                                 car: cars(:corolla), trip: trips(:commute))
    Membership.create!(user: users(:alice), carpool_group: group, cost_split_percentage: 0.50)
    assert_not group.splits_complete?
  end

  test "has many users through memberships" do
    assert_includes @group.users, users(:alice)
    assert_includes @group.users, users(:bob)
    assert_includes @group.users, users(:carol)
  end
end
