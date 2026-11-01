
import React, {
  useMemo,
  useState,
  useEffect
} from 'react';

import Sidebar from './components/Sidebar.jsx';
import Header from './components/Header.jsx';

import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Inventory from './pages/Inventory.jsx';
import Monitoring from './pages/Monitoring.jsx';
import AIPredictions from './pages/AIPredictions.jsx';
import FoodReference from './pages/FoodReference.jsx';
import FoodDetails from './pages/FoodDetails.jsx';
import Settings from './pages/Settings.jsx';
import HelpSupport from './pages/HelpSupport.jsx';

import {
  foodItems as initialFoodItems
} from './data/foodData.js';

const INVENTORY_STORAGE_KEY = 'freshbox-inventory';
const USER_STORAGE_KEY = 'freshbox-user';
const API_BASE_URL = (
  import.meta.env.VITE_FRESHBOX_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

// Safely read saved user
function getSavedUser() {
  try {
    const savedUser = localStorage.getItem(
      USER_STORAGE_KEY
    );

    if (!savedUser) {
      return null;
    }

    const parsedUser = JSON.parse(savedUser);

    if (
      parsedUser &&
      typeof parsedUser.email === 'string' &&
      typeof parsedUser.name === 'string'
    ) {
      return parsedUser;
    }

    localStorage.removeItem(USER_STORAGE_KEY);

    return null;
  } catch {
    return null;
  }
}

// Safely load saved food inventory
function getSavedInventory() {
  try {
    const savedInventory = localStorage.getItem(
      INVENTORY_STORAGE_KEY
    );

    if (savedInventory !== null) {
      const parsedInventory = JSON.parse(
        savedInventory
      );

      if (Array.isArray(parsedInventory)) {
        // Filter out old placeholder demo items (Apple, Mango, Carrot, Broccoli)
        // while preserving any user-added food records and external reference items.
        const legacyDemoNames = new Set(['Apple', 'Mango', 'Carrot', 'Broccoli']);
        const cleaned = parsedInventory.filter((item) => {
          if (
            legacyDemoNames.has(item.name) &&
            (typeof item.id === 'number' || !item.id.toString().startsWith('food-'))
          ) {
            return false;
          }
          return true;
        });

        if (cleaned.length > 0) {
          return cleaned;
        }
      }
    }
  } catch {
    // Use initial reference inventory if saved data is unavailable.
  }

  return initialFoodItems;
}

// Create a unique food ID
function createFoodId() {
  return `food-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

// Convert form data into an inventory item
function createFoodItem(foodData) {
  const addedAt =
    foodData.addedAt ||
    new Date().toISOString();

  const quantityKg = Number(
    foodData.quantityKg
  );

  return {
    id: createFoodId(),

    name: String(
      foodData.name || ''
    ).trim(),

    category: foodData.category || 'Fruit',

    quantityKg,

    addedAt,

    emoji: foodData.emoji || '🥗',

    color: foodData.color || '#eaf4e8',

    // Illustrative values until the prediction
    // algorithm is connected.
    score: Number(
      foodData.score ?? 100
    ),

    days: Number(
      foodData.days ?? 5
    ),

    status: foodData.status || 'Fresh',

    notes: foodData.notes || '',

    quantity: `${quantityKg} kg`
  };
}

export default function App() {
  const [user, setUser] = useState(
    getSavedUser
  );

  // Shared inventory for every page
  const [items, setItems] = useState(
    getSavedInventory
  );

  const [page, setPage] = useState(
    'Dashboard'
  );

  const [category, setCategory] = useState(
    'All items'
  );

  const [search, setSearch] = useState('');

  const [selected, setSelected] = useState(null);

  // Automatically sync live inventory and AI shelf-life predictions from API every 2 seconds
  useEffect(() => {
    let active = true;
    let timeoutId;

    async function syncLiveInventory() {
      try {
        const res = await fetch(`${API_BASE_URL}/api/inventory/live`);
        if (res.ok) {
          const liveData = await res.json();
          if (active && Array.isArray(liveData) && liveData.length > 0) {
            setItems(liveData);
          }
        }
      } catch {
        // Continue using local state when offline
      } finally {
        if (active) {
          timeoutId = window.setTimeout(syncLiveInventory, 2000);
        }
      }
    }

    syncLiveInventory();
    return () => {
      active = false;
      window.clearTimeout(timeoutId);
    };
  }, []);

  // Save inventory whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem(
        INVENTORY_STORAGE_KEY,
        JSON.stringify(items)
      );
    } catch {
      // Continue using React state if storage fails.
    }
  }, [items]);

  // Filter inventory by category and search
  const filtered = useMemo(() => {
    return items.filter((item) => {
      const matchesCategory =
        category === 'All items' ||
        item.category === category ||
        item.status === category;

      const matchesSearch = String(
        item.name || ''
      )
        .toLowerCase()
        .includes(search.toLowerCase());

      return (
        matchesCategory &&
        matchesSearch
      );
    });
  }, [items, category, search]);

  // Add food
  const handleAddFood = (foodData) => {
    if (
      !foodData ||
      !String(foodData.name || '').trim() ||
      !Number.isFinite(
        Number(foodData.quantityKg)
      ) ||
      Number(foodData.quantityKg) <= 0
    ) {
      alert(
        'Please enter a food name and a valid quantity.'
      );

      return;
    }

    const newFood = createFoodItem(foodData);

    setItems((previousItems) => [
      newFood,
      ...previousItems
    ]);

    // Reset inventory filters
    setCategory('All items');
    setSearch('');

    alert(
      `${newFood.name} added to FreshBox!`
    );
  };

  // Update existing food
  const handleUpdateFood = (updatedFood) => {
    if (!updatedFood?.id) {
      return;
    }

    setItems((previousItems) =>
      previousItems.map((item) =>
        item.id === updatedFood.id
          ? {
              ...item,
              ...updatedFood,

              // Keep quantity fields synchronized
              quantityKg:
                updatedFood.quantityKg !== undefined
                  ? Number(
                      updatedFood.quantityKg
                    )
                  : item.quantityKg,

              quantity:
                updatedFood.quantityKg !== undefined
                  ? `${Number(
                      updatedFood.quantityKg
                    )} kg`
                  : item.quantity
            }
          : item
      )
    );

    setSelected((previousSelected) =>
      previousSelected?.id === updatedFood.id
        ? {
            ...previousSelected,
            ...updatedFood
          }
        : previousSelected
    );
  };

  // Delete food
  const handleDeleteFood = (foodId) => {
    if (!foodId) {
      return;
    }

    setItems((previousItems) =>
      previousItems.filter(
        (item) => item.id !== foodId
      )
    );

    setSelected(null);
  };

  // Login
  const handleLogin = (userData) => {
    const newUser = {
      name: userData.name,
      email: userData.email
    };

    setUser(newUser);

    try {
      localStorage.setItem(
        USER_STORAGE_KEY,
        JSON.stringify(newUser)
      );
    } catch {
      // Continue using React state.
    }

    setPage('Dashboard');
    setCategory('All items');
    setSearch('');
    setSelected(null);
  };

  // Logout
  const handleLogout = () => {
    setUser(null);

    try {
      localStorage.removeItem(
        USER_STORAGE_KEY
      );
    } catch {
      // Ignore storage errors.
    }

    setPage('Dashboard');
    setCategory('All items');
    setSearch('');
    setSelected(null);
  };

  // Sidebar navigation
  const handleNavigate = (newPage) => {
    setPage(newPage);

    setCategory('All items');
    setSearch('');
    setSelected(null);
  };

  // Show login if user is not authenticated
  if (!user) {
    return (
      <Login
        onLogin={handleLogin}
      />
    );
  }

  return (
    <div className="app">

      {/* Sidebar */}
      <Sidebar
        active={page}
        onNavigate={handleNavigate}
      />

      {/* Main Content */}
      <main>
        <Header
          page={page}
          user={user}
          onLogout={handleLogout}
        />

        <div className="page">

          {/* Dashboard */}
          {page === 'Dashboard' && (
            <Dashboard
              items={items}
              onSelect={setSelected}
              onAll={() =>
                handleNavigate(
                  'Food Inventory'
                )
              }
              onAddFood={handleAddFood}
            />
          )}

          {/* Food Inventory */}
          {page === 'Food Inventory' && (
            <Inventory
              items={filtered}
              category={category}
              setCategory={setCategory}
              search={search}
              setSearch={setSearch}
              onSelect={setSelected}
              onUpdateFood={handleUpdateFood}
              onDeleteFood={handleDeleteFood}
            />
          )}

          {/* Live Monitoring */}
          {page === 'Live Monitoring' && (
            <Monitoring
              items={items}
            />
          )}

          {/* AI Predictions */}
          {page === 'AI Predictions' && (
            <AIPredictions
              items={items}
            />
          )}

          {/* Food Reference */}
          {page === 'Food Reference' && (
            <FoodReference
              items={items}
            />
          )}

          {/* Settings */}
          {page === 'Settings' && (
            <Settings />
          )}

          {/* Help & Support */}
          {page === 'Help & support' && (
            <HelpSupport />
          )}

        </div>
      </main>

      {/* Food Details Modal */}
      <FoodDetails
        item={selected}
        onClose={() => setSelected(null)}
        onUpdate={handleUpdateFood}
        onDelete={handleDeleteFood}
      />

    </div>
  );
}
