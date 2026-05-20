require "test_helper"

class CarTest < ActiveSupport::TestCase
  test "valid with all required attributes" do
    car = Car.new(name: "Honda Civic", cost_per_km: 1.80)
    assert car.valid?
  end

  test "invalid without name" do
    car = Car.new(cost_per_km: 1.80)
    assert_not car.valid?
    assert_includes car.errors[:name], "can't be blank"
  end

  test "invalid without cost_per_km" do
    car = Car.new(name: "Civic")
    assert_not car.valid?
    assert_includes car.errors[:cost_per_km], "can't be blank"
  end

  test "cost_per_km must be positive" do
    car = Car.new(name: "Civic", cost_per_km: 0)
    assert_not car.valid?
    assert_includes car.errors[:cost_per_km], "must be greater than 0"
  end

  test "cost_per_km cannot be negative" do
    car = Car.new(name: "Civic", cost_per_km: -1)
    assert_not car.valid?
  end

  test "has many carpool groups" do
    assert_includes cars(:corolla).carpool_groups, carpool_groups(:may_group)
  end
end
