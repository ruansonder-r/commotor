# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[8.1].define(version: 2026_05_20_064914) do
  create_table "carpool_groups", force: :cascade do |t|
    t.integer "car_id", null: false
    t.datetime "created_at", null: false
    t.date "month"
    t.string "name"
    t.integer "trip_id", null: false
    t.datetime "updated_at", null: false
    t.index ["car_id"], name: "index_carpool_groups_on_car_id"
    t.index ["trip_id"], name: "index_carpool_groups_on_trip_id"
  end

  create_table "cars", force: :cascade do |t|
    t.decimal "cost_per_km"
    t.datetime "created_at", null: false
    t.string "name"
    t.datetime "updated_at", null: false
  end

  create_table "memberships", force: :cascade do |t|
    t.integer "carpool_group_id", null: false
    t.decimal "cost_split_percentage"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.integer "user_id", null: false
    t.index ["carpool_group_id"], name: "index_memberships_on_carpool_group_id"
    t.index ["user_id", "carpool_group_id"], name: "index_memberships_on_user_id_and_carpool_group_id", unique: true
    t.index ["user_id"], name: "index_memberships_on_user_id"
  end

  create_table "trip_logs", force: :cascade do |t|
    t.integer "carpool_group_id", null: false
    t.datetime "created_at", null: false
    t.datetime "occurred_at"
    t.integer "recorded_by_user_id"
    t.integer "trip_count"
    t.datetime "updated_at", null: false
    t.index ["carpool_group_id"], name: "index_trip_logs_on_carpool_group_id"
  end

  create_table "trips", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.decimal "distance_km"
    t.string "name"
    t.datetime "updated_at", null: false
  end

  create_table "users", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "display_name"
    t.string "email"
    t.string "uid"
    t.datetime "updated_at", null: false
    t.index ["email"], name: "index_users_on_email", unique: true
    t.index ["uid"], name: "index_users_on_uid", unique: true
  end

  add_foreign_key "carpool_groups", "cars"
  add_foreign_key "carpool_groups", "trips"
  add_foreign_key "memberships", "carpool_groups"
  add_foreign_key "memberships", "users"
  add_foreign_key "trip_logs", "carpool_groups"
end
