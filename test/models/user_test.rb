require "test_helper"

class UserTest < ActiveSupport::TestCase
  test "valid with all required attributes" do
    user = User.new(uid: "uid_new", display_name: "New User", email: "new@example.com")
    assert user.valid?
  end

  test "invalid without uid" do
    user = User.new(display_name: "A", email: "a@example.com")
    assert_not user.valid?
    assert_includes user.errors[:uid], "can't be blank"
  end

  test "invalid without display_name" do
    user = User.new(uid: "uid_x", email: "a@example.com")
    assert_not user.valid?
    assert_includes user.errors[:display_name], "can't be blank"
  end

  test "invalid without email" do
    user = User.new(uid: "uid_x", display_name: "A")
    assert_not user.valid?
    assert_includes user.errors[:email], "can't be blank"
  end

  test "uid must be unique" do
    duplicate = User.new(uid: users(:alice).uid, display_name: "Other", email: "other@example.com")
    assert_not duplicate.valid?
    assert_includes duplicate.errors[:uid], "has already been taken"
  end

  test "email must be unique" do
    duplicate = User.new(uid: "uid_unique", display_name: "Other", email: users(:alice).email)
    assert_not duplicate.valid?
    assert_includes duplicate.errors[:email], "has already been taken"
  end

  test "has many memberships" do
    assert_equal 1, users(:alice).memberships.count
  end

  test "has many carpool groups through memberships" do
    assert_includes users(:alice).carpool_groups, carpool_groups(:may_group)
  end
end
