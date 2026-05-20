class CarpoolGroup < ApplicationRecord
  belongs_to :car
  belongs_to :trip
  has_many :memberships, dependent: :destroy
  has_many :users, through: :memberships
  has_many :trip_logs, dependent: :destroy

  validates :name, presence: true
  validates :month, presence: true

  def trip_cost
    car.cost_per_km * trip.distance_km
  end

  def monthly_tally
    trip_cost * trip_logs.sum(:trip_count)
  end

  def splits_complete?
    (memberships.sum(:cost_split_percentage).to_f - 1.0).abs < 0.001
  end
end
