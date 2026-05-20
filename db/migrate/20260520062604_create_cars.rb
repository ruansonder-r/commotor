class CreateCars < ActiveRecord::Migration[8.1]
  def change
    create_table :cars do |t|
      t.string :name
      t.decimal :cost_per_km

      t.timestamps
    end
  end
end
