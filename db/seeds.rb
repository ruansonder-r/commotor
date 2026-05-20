car = Car.find_or_create_by!(name: "V40 1.6") do |c|
  c.cost_per_km = 1.6
end

trip = Trip.find_or_create_by!(name: "Commute") do |t|
  t.distance_km = 70.0
end

group = CarpoolGroup.find_or_create_by!(name: "Commute", month: Date.new(2026, 5, 1)) do |g|
  g.car = car
  g.trip = trip
end

puts "Seeded: 1 car, 1 trip, 1 group"
puts "  Trip cost per leg: R#{'%.2f' % group.trip_cost}"
