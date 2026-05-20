class User < ApplicationRecord
  has_many :memberships, dependent: :destroy
  has_many :carpool_groups, through: :memberships
  has_many :recorded_trip_logs, class_name: "TripLog", foreign_key: :recorded_by_user_id, dependent: :destroy

  validates :uid, presence: true, uniqueness: true
  validates :email, presence: true, uniqueness: true
  validates :display_name, presence: true
end
