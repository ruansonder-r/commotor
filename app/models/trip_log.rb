class TripLog < ApplicationRecord
  belongs_to :carpool_group
  belongs_to :recorded_by, class_name: "User", foreign_key: :recorded_by_user_id

  validates :occurred_at, presence: true
  validates :trip_count, numericality: { only_integer: true, other_than: 0 }
  validate :group_splits_are_complete

  before_validation :set_defaults

  private

  def set_defaults
    self.occurred_at ||= Time.current
    self.trip_count ||= 1
  end

  def group_splits_are_complete
    return unless carpool_group.present?

    unless carpool_group.splits_complete?
      errors.add(:base, "cannot log a trip until all membership splits sum to 100%")
    end
  end
end
