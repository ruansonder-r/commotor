class CreateCarpoolGroups < ActiveRecord::Migration[8.1]
  def change
    create_table :carpool_groups do |t|
      t.string :name
      t.date :month
      t.references :car, null: false, foreign_key: true
      t.references :trip, null: false, foreign_key: true

      t.timestamps
    end
  end
end
