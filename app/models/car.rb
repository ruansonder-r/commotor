class Car < ApplicationRecord
  has_many :carpool_groups, dependent: :restrict_with_error

  validates :name, presence: true
  validates :cost_per_km, presence: true, numericality: { greater_than: 0 }
end
