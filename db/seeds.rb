alice = User.find_or_create_by!(uid: "uid_alice") do |u|
  u.display_name = "Alice Smith"
  u.email = "alice@example.com"
end

bob = User.find_or_create_by!(uid: "uid_bob") do |u|
  u.display_name = "Bob Jones"
  u.email = "bob@example.com"
end

carol = User.find_or_create_by!(uid: "uid_carol") do |u|
  u.display_name = "Carol White"
  u.email = "carol@example.com"
end

car = Car.find_or_create_by!(name: "Toyota Corolla") do |c|
  c.cost_per_km = 2.50
end

trip = Trip.find_or_create_by!(name: "Morning Commute") do |t|
  t.distance_km = 40.0
end

group = CarpoolGroup.find_or_create_by!(name: "Morning Commute Group", month: Date.new(2026, 5, 1)) do |g|
  g.car = car
  g.trip = trip
end

Membership.find_or_create_by!(user: alice, carpool_group: group) { |m| m.cost_split_percentage = 0.30 }
Membership.find_or_create_by!(user: bob,   carpool_group: group) { |m| m.cost_split_percentage = 0.40 }
Membership.find_or_create_by!(user: carol, carpool_group: group) { |m| m.cost_split_percentage = 0.30 }

10.times do |i|
  TripLog.create!(
    carpool_group: group,
    recorded_by: [ alice, bob, carol ].rotate(i).first,
    occurred_at: Date.new(2026, 5, 1) + i.days,
    trip_count: 1
  )
end

puts "Seeded: 3 users, 1 car, 1 trip, 1 group, 3 memberships, 10 trip logs"
puts "  Trip cost per leg:  R#{'%.2f' % group.trip_cost}"
puts "  Monthly tally:      R#{'%.2f' % group.monthly_tally}"
