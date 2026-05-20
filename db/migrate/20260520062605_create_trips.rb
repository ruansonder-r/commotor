class CreateTrips < ActiveRecord::Migration[8.1]
  def change
    create_table :trips do |t|
      t.string :name
      t.decimal :distance_km

      t.timestamps
    end
  end
end
