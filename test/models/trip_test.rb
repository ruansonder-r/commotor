require "test_helper"

class TripTest < ActiveSupport::TestCase
  test "valid with all required attributes" do
    trip = Trip.new(name: "Evening Return", distance_km: 25.0)
    assert trip.valid?
  end

  test "invalid without name" do
    trip = Trip.new(distance_km: 25.0)
    assert_not trip.valid?
    assert_includes trip.errors[:name], "can't be blank"
  end

  test "invalid without distance_km" do
    trip = Trip.new(name: "Route A")
    assert_not trip.valid?
    assert_includes trip.errors[:distance_km], "can't be blank"
  end

  test "distance_km must be positive" do
    trip = Trip.new(name: "Route A", distance_km: 0)
    assert_not trip.valid?
    assert_includes trip.errors[:distance_km], "must be greater than 0"
  end

  test "distance_km cannot be negative" do
    trip = Trip.new(name: "Route A", distance_km: -5)
    assert_not trip.valid?
  end

  test "has many carpool groups" do
    assert_includes trips(:commute).carpool_groups, carpool_groups(:may_group)
  end
end
