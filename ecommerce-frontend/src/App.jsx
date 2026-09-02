import AgentInfo from './pages/AgentInfo';

import React from 'react';







import { Routes, Route } from 'react-router-dom';







import Navbar from './components/Navbar';
import ChatbotWidget from './components/ChatbotWidget';







import Home from './pages/Home';







import ProductDetails from './pages/ProductDetails';







import AddProduct from './pages/AddProduct';







import EditProduct from './pages/EditProduct';







import Cart from './pages/Cart';







import Orders from './pages/Orders';







import Login from './pages/Login';







import Register from './pages/Register';







import Checkout from './pages/Checkout';







import { PrivateRoute, AdminRoute } from './components/RouteGuards';







export default function App() {







  return (







    <div className="app-shell">







      <Navbar />







      <main className="app-content">







        <Routes>

          <Route path="/agent-info" element={<AgentInfo />} />







          <Route path="/" element={<Home />} />







          <Route path="/products/:id" element={<ProductDetails />} />







          <Route path="/login" element={<Login />} />







          <Route path="/register" element={<Register />} />







          <Route







            path="/add-product"







            element={







              <AdminRoute>







                <AddProduct />







              </AdminRoute>







            }







          />







          <Route







            path="/edit-product/:id"







            element={







              <AdminRoute>







                <EditProduct />







              </AdminRoute>







            }







          />







          <Route







            path="/cart"







            element={







              <PrivateRoute>







                <Cart />







              </PrivateRoute>







            }







          />







          <Route







            path="/orders"







            element={







              <PrivateRoute>







                <Orders />







              </PrivateRoute>







            }







          />







          <Route







            path="/checkout"



            element={<Checkout />}



          />



        </Routes>



      </main>
      <ChatbotWidget />
    </div>



  );



}



