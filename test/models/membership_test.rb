require "test_helper"

class MembershipTest < ActiveSupport::TestCase
  test "invalid without cost_split_percentage" do
    m = Membership.new(user: users(:alice), carpool_group: carpool_groups(:may_group))
    assert_not m.valid?
    assert_includes m.errors[:cost_split_percentage], "can't be blank"
  end

  test "cost_split_percentage must be greater than 0" do
    m = Membership.new(user: users(:alice), carpool_group: carpool_groups(:may_group),
                       cost_split_percentage: 0)
    assert_not m.valid?
    assert_includes m.errors[:cost_split_percentage], "must be greater than 0"
  end

  test "cost_split_percentage cannot exceed 1.0" do
    m = Membership.new(user: users(:alice), carpool_group: carpool_groups(:may_group),
                       cost_split_percentage: 1.1)
    assert_not m.valid?
    assert_includes m.errors[:cost_split_percentage], "must be less than or equal to 1"
  end

  test "a user cannot be a member of the same group twice" do
    duplicate = Membership.new(user: users(:alice), carpool_group: carpool_groups(:may_group),
                               cost_split_percentage: 0.10)
    assert_not duplicate.valid?
    assert_includes duplicate.errors[:user_id], "has already been taken"
  end

  test "adding a split that would push group total above 100% is rejected" do
    group = CarpoolGroup.create!(name: "New Group", month: Date.new(2026, 6, 1),
                                 car: cars(:corolla), trip: trips(:commute))
    Membership.create!(user: users(:alice), carpool_group: group, cost_split_percentage: 0.70)

    overflow = Membership.new(user: users(:bob), carpool_group: group, cost_split_percentage: 0.40)
    assert_not overflow.valid?
    assert_includes overflow.errors[:cost_split_percentage], "would cause group total to exceed 100%"
  end

  test "amount_owed returns share of monthly tally" do
    # may_group tally = 2 logs × R100/trip = R200; alice share = 30% → R60
    alice_membership = memberships(:alice_may)
    assert_in_delta 60.0, alice_membership.amount_owed, 0.01
  end
end
