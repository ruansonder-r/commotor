class Membership < ApplicationRecord
  belongs_to :user
  belongs_to :carpool_group

  validates :cost_split_percentage, presence: true,
            numericality: { greater_than: 0, less_than_or_equal_to: 1 }
  validates :user_id, uniqueness: { scope: :carpool_group_id }
  validate :total_does_not_exceed_one

  def amount_owed
    carpool_group.monthly_tally * cost_split_percentage
  end

  private

  def total_does_not_exceed_one
    return unless cost_split_percentage.present? && carpool_group.present?

    other_total = carpool_group.memberships.where.not(id: id).sum(:cost_split_percentage).to_f
    if other_total + cost_split_percentage.to_f > 1.001
      errors.add(:cost_split_percentage, "would cause group total to exceed 100%")
    end
  end
end
